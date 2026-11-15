#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[매일 아침 8시 정각 카카오톡 AI 브리핑 & 유튜브 최신 영상 자동 수집 스크립트]
- 고정된 기본 유튜버 없이, 매일 유튜브 전체에서 최신 국내/해외 AI·에이전트·실무 영상을 실시간 탐색합니다.
- 수집된 데이터에 '브리핑 생성일자'와 '유튜브 업로드 시점'을 명확히 기록하여 briefing_data.json으로 저장합니다.
- GitHub Actions 대기열 지연을 방지하기 위해 07:15 KST경 미리 수집·배포 후 정확히 08:00:00 KST에 카톡을 발송합니다.
"""

import os
import re
import sys
import time
import json
import urllib.parse
import datetime
import requests

KST = datetime.timezone(datetime.timedelta(hours=9))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KAKAO_TOKEN_FILE = os.path.join(BASE_DIR, "kakao_token.json")
BRIEFING_DATA_FILE = os.path.join(BASE_DIR, "briefing_data.json")

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")

# 스팸/주식 영상 필터 키워드
SPAM_KEYWORDS = ["주가전망", "급등주", "매도", "매수", "목표가", "선물거래", "코인", "상한가", "종목"]

DOMESTIC_QUERIES = [
    ("AI 에이전트", ["AI에이전트", "업무자동화", "실무"]),
    ("클로드 코드 AI", ["클로드코드", "AI코딩", "실무"]),
    ("제미나이 AI 활용", ["제미나이", "구글AI", "실무"]),
    ("챗GPT 실무 자동화", ["챗GPT", "업무자동화", "프롬프트"]),
    ("AI 바이브코딩 실무", ["바이브코딩", "웹빌드", "에이전트"]),
]

GLOBAL_QUERIES = [
    ("AI Agents workflow tutorial", ["AI에이전트", "글로벌", "워크플로"]),
    ("Claude Code agentic workflow", ["클로드코드", "앤트로픽", "에이전트"]),
    ("Gemini AI Studio workflow", ["구글AI", "제미나이", "멀티모달"]),
    ("MCP Model Context Protocol AI", ["MCP", "에이전트", "자동화"]),
]


def get_now_kst():
    return datetime.datetime.now(KST)


def get_current_date_info():
    now = get_now_kst()
    days = ["월", "화", "수", "목", "금", "토", "일"]
    day_str = days[now.weekday()]
    return {
        "full_str": f"{now.year}년 {now.month:02d}월 {now.day:02d}일 ({day_str})",
        "short_str": f"{now.year}.{now.month:02d}.{now.day:02d}",
        "month_day": f"{now.month}월 {now.day}일",
        "timestamp": now.strftime("%Y-%m-%d %H:%M KST"),
    }


def translate_en_to_ko(text):
    """무료 Google GTX 번역 엔드포인트를 사용해 영어 제목/요약을 자연스러운 한국어로 변환"""
    if not text or not text.strip():
        return text
    try:
        q = urllib.parse.quote(text.strip())
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ko&dt=t&q={q}"
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            translated = "".join([part[0] for part in data[0] if part and part[0]])
            return translated.strip()
    except Exception:
        pass
    return text


def build_summary_points(title, snippet, channel, is_global=False, orig_title=""):
    """영상 제목과 설명 스니펫에서 3줄 핵심 요약 생성"""
    clean_snip = re.sub(r"\s+", " ", (snippet or "")).strip()
    points = []

    if is_global:
        ko_snip = translate_en_to_ko(clean_snip) if clean_snip else ""
        points.append(f"글로벌 채널 '{channel}'의 최신 AI 트렌드 영상 (원제: {orig_title})")
        if ko_snip:
            points.append(f"핵심 내용: {ko_snip[:110]}{'...' if len(ko_snip) > 110 else ''}")
        else:
            points.append(f"'{title}' 주제의 글로벌 실무 워크플로 및 최신 에이전트 활용법 분석")
        points.append("실무 팁: 유튜브 자막 자동번역(한국어) 기능을 켜고 시청하시면 핵심 프롬프트와 화면 구성을 바로 적용할 수 있습니다.")
    else:
        points.append(f"'{channel}' 채널에서 업로드한 최신 AI 실무·트렌드 분석 영상")
        if clean_snip:
            points.append(f"핵심 요약: {clean_snip[:115]}{'...' if len(clean_snip) > 115 else ''}")
        else:
            points.append(f"'{title}' 관련 실전 세팅 및 단계별 활용 노하우 정리")
        points.append("실무 적용: 영상 본문과 고정 댓글의 프롬프트·템플릿 링크를 확인하여 업무 자동화에 즉시 테스트해 보세요.")

    return points


def search_youtube_recent(queries, is_global=False, max_total=8):
    """특정 유튜버에 국한하지 않고 유튜브 전체에서 최근 업로드된 AI 영상을 탐색"""
    date_info = get_current_date_info()
    briefing_date_short = date_info["short_str"]
    briefing_month_day = date_info["month_day"]

    hl = "en" if is_global else "ko"
    gl = "US" if is_global else "KR"
    lang_header = "en-US,en;q=0.9" if is_global else "ko-KR,ko;q=0.9"

    headers = {
        "Accept-Language": lang_header,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    seen_video_ids = set()
    seen_channels = set()
    results = []

    for query_text, default_tags in queries:
        q_encoded = urllib.parse.quote(query_text)
        # sp=EgIIAw%253D%253D : 이번 주 업로드된 최신 영상 필터
        url = f"https://www.youtube.com/results?search_query={q_encoded}&sp=EgIIAw%253D%253D&hl={hl}&gl={gl}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            match = re.search(r"var ytInitialData = (\{.*?\});</script>", resp.text)
            if not match:
                continue
            data = json.loads(match.group(1))
            sections = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            if not sections:
                continue
            items = sections[0].get("itemSectionRenderer", {}).get("contents", [])

            per_query_count = 0
            for item in items:
                v = item.get("videoRenderer")
                if not v:
                    continue

                vid = v.get("videoId", "")
                title_runs = v.get("title", {}).get("runs", [])
                orig_title = title_runs[0].get("text", "") if title_runs else ""
                owner_runs = v.get("ownerText", {}).get("runs", [])
                channel = owner_runs[0].get("text", "") if owner_runs else ""
                pub_time = v.get("publishedTimeText", {}).get("simpleText", "최근 업로드")
                duration = v.get("lengthText", {}).get("simpleText", "")

                # 쇼츠(길이가 없거나 너무 짧은 항목), 중복 채널/영상, 주식 스팸 제외
                if not vid or not orig_title or not channel or not duration:
                    continue
                if vid in seen_video_ids or channel in seen_channels:
                    continue
                if any(spam in orig_title for spam in SPAM_KEYWORDS):
                    continue

                snippet = ""
                snippets_list = v.get("detailedMetadataSnippets", [])
                if snippets_list:
                    snip_runs = snippets_list[0].get("snippetText", {}).get("runs", [])
                    snippet = "".join([r.get("text", "") for r in snip_runs])

                if any(spam in snippet for spam in SPAM_KEYWORDS):
                    continue

                if is_global:
                    display_title = translate_en_to_ko(orig_title)
                    pub_ko = (
                        pub_time.replace(" days ago", "일 전")
                        .replace(" day ago", "일 전")
                        .replace(" hours ago", "시간 전")
                        .replace(" hour ago", "시간 전")
                        .replace("Streamed ", "스트리밍 ")
                    )
                else:
                    display_title = orig_title
                    pub_ko = pub_time

                summary_points = build_summary_points(
                    display_title, snippet, channel, is_global=is_global, orig_title=orig_title
                )

                seen_video_ids.add(vid)
                seen_channels.add(channel)

                prefix = "glob" if is_global else "dom"
                idx_num = len(results) + 1
                results.append(
                    {
                        "id": f"{prefix}_{briefing_date_short.replace('.', '')}_{idx_num}",
                        "title": display_title,
                        "originalTitle": orig_title,
                        "channel": channel,
                        "channelUrl": f"https://www.youtube.com/results?search_query={urllib.parse.quote(channel)}",
                        "duration": f"약 {duration}",
                        "publishedAt": pub_ko,
                        "briefingDate": briefing_date_short,
                        "updatedAt": f"{briefing_month_day} 브리핑 · {pub_ko}",
                        "tags": default_tags,
                        "videoUrl": f"https://www.youtube.com/watch?v={vid}",
                        "summaryPoints": summary_points,
                        "details": f"[{briefing_date_short} 자 브리핑 수집] {channel} 채널의 '{display_title}' 영상입니다. (유튜브 업로드: {pub_ko})",
                    }
                )
                per_query_count += 1
                if len(results) >= max_total or per_query_count >= 3:
                    break
        except Exception as e:
            print(f">> 검색 중 예외 ({query_text}): {e}")

        if len(results) >= max_total:
            break

    return results


def collect_and_save_briefing():
    """유튜브에서 최신 국내/해외 AI 영상을 수집하고 briefing_data.json으로 저장"""
    date_info = get_current_date_info()
    print(f">> [{date_info['timestamp']}] 유튜브 최신 AI 영상 탐색 시작...")

    domestic_items = search_youtube_recent(DOMESTIC_QUERIES, is_global=False, max_total=8)
    global_items = search_youtube_recent(GLOBAL_QUERIES, is_global=True, max_total=6)

    payload = {
        "briefingDate": date_info["full_str"],
        "briefingDateShort": date_info["short_str"],
        "generatedAt": date_info["timestamp"],
        "domesticCount": len(domestic_items),
        "globalCount": len(global_items),
        "domesticItems": domestic_items,
        "globalItems": global_items,
    }

    with open(BRIEFING_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f">> briefing_data.json 저장 완료! (국내 {len(domestic_items)}건 / 해외 {len(global_items)}건)"
    )
    return payload


def load_or_collect_briefing():
    if os.path.exists(BRIEFING_DATA_FILE):
        try:
            with open(BRIEFING_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 오늘 날짜 데이터인지 확인
            today_short = get_current_date_info()["short_str"]
            if data.get("briefingDateShort") == today_short and data.get("domesticItems"):
                return data
        except Exception:
            pass
    return collect_and_save_briefing()


def load_tokens():
    if os.path.exists(KAKAO_TOKEN_FILE):
        try:
            with open(KAKAO_TOKEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN", "")
    access_token = os.environ.get("KAKAO_ACCESS_TOKEN", "")
    if refresh_token:
        return {"access_token": access_token, "refresh_token": refresh_token}
    return None


def refresh_kakao_token(tokens):
    """리프레시 토큰으로 액세스 토큰 영구 자동 갱신"""
    if not tokens or not tokens.get("refresh_token") or not REST_API_KEY:
        return tokens

    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "client_secret": CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
    }
    resp = requests.post(url, data=data, timeout=10)
    result = resp.json()
    if "access_token" in result:
        tokens["access_token"] = result["access_token"]
        if "refresh_token" in result:
            tokens["refresh_token"] = result["refresh_token"]
        try:
            with open(KAKAO_TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(tokens, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        print(">> 카카오 액세스 토큰 자동 갱신 성공!")
    else:
        print(">> 토큰 갱신 응답 오류:", result)
    return tokens


def generate_briefing_message(briefing_data):
    date_str = briefing_data.get("briefingDate", get_current_date_info()["full_str"])
    short_date = briefing_data.get("briefingDateShort", get_current_date_info()["short_str"])
    dom_items = briefing_data.get("domesticItems", [])
    glob_items = briefing_data.get("globalItems", [])

    total_cnt = len(dom_items) + len(glob_items)

    lines = [
        "[🚀 데일리 AI 실무 트렌드 브리핑]",
        f"📅 {date_str} 아침 8시 브리핑",
        f"📌 [{short_date} 일자 신규 수집 데이터]",
        "",
        f"📢 오늘 발굴한 최신 AI 영상: 총 {total_cnt}건!",
        f"(국내 유튜버 {len(dom_items)}건 / 해외 글로벌 {len(glob_items)}건)",
        "",
        "🇰🇷 [오늘의 국내 AI 유튜브 픽]",
    ]

    for idx, item in enumerate(dom_items[:4], start=1):
        title_short = item["title"][:34] + ("..." if len(item["title"]) > 34 else "")
        lines.append(f"{idx}. [{item['channel']}] ({item.get('publishedAt', '최신')})")
        lines.append(f"   • {title_short}")

    lines.append("")
    lines.append("🌏 [해외 글로벌 최신 트렌드]")
    for item in glob_items[:2]:
        title_short = item["title"][:32] + ("..." if len(item["title"]) > 32 else "")
        lines.append(f"• {item['channel']} ({item.get('publishedAt', '최신')}): {title_short}")

    lines.append("")
    lines.append(f"✅ 앱에서 '{short_date} 일자' 전체 요약 & 영상을 확인하세요!")

    return "\n".join(lines)


def send_kakao_memo(access_token, message_text, short_date):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # 캐시 방지를 위해 날짜 쿼리 파라미터 추가
    app_url = f"https://kjhan0430-ops.github.io/daily-ai-briefing/?date={short_date}"

    payload = {
        "template_object": json.dumps(
            {
                "object_type": "text",
                "text": message_text,
                "link": {"web_url": app_url, "mobile_web_url": app_url},
                "button_title": f"{short_date} AI 대시보드 열기",
            },
            ensure_ascii=False,
        )
    }

    resp = requests.post(url, headers=headers, data=payload, timeout=10)
    if resp.status_code == 200 and resp.json().get("result_code") == 0:
        print(f"✅ [{get_now_kst()}] 카카오톡 메시지 전송 성공!")
        return True
    else:
        print(f"❌ 전송 실패: {resp.status_code} - {resp.text}")
        return False


def wait_until_8am_kst():
    """
    GitHub Actions 스케줄러가 07:15~07:55 KST 사이에 미리 켜지면,
    정확히 한국 시간 08:00:00가 될 때까지 대기한 후 즉시 발송합니다.
    """
    now = get_now_kst()
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    diff_sec = (target - now).total_seconds()

    # 만약 오전 7시~8시 사이에 실행되었다면 08:00:00 정각까지 대기
    if 0 < diff_sec <= 3600:
        print(f">> 현재 한국 시각 {now.strftime('%H:%M:%S')} — 아침 08:00:00 정각 발송을 위해 {int(diff_sec)}초 대기합니다...")
        time.sleep(diff_sec)
        print(f">> 목표 시각 도달! ({get_now_kst().strftime('%H:%M:%S')}) 즉시 발송합니다.")
    else:
        print(f">> 현재 한국 시각 {now.strftime('%H:%M:%S')} — 대기 없이 즉시 발송합니다.")


def main():
    args = sys.argv[1:]
    collect_only = "--collect-only" in args
    send_only = "--send-only" in args
    wait_8am = "--wait-8am" in args

    if collect_only:
        collect_and_save_briefing()
        return

    if send_only:
        briefing_data = load_or_collect_briefing()
    else:
        briefing_data = collect_and_save_briefing()

    tokens = load_tokens()
    if not tokens or not tokens.get("refresh_token"):
        print("⚠️ 카카오 토큰 정보가 없습니다.")
        sys.exit(1)

    tokens = refresh_kakao_token(tokens)
    if not tokens.get("access_token"):
        print("❌ 유효한 액세스 토큰을 얻지 못했습니다.")
        sys.exit(1)

    if wait_8am:
        wait_until_8am_kst()

    msg = generate_briefing_message(briefing_data)
    short_date = briefing_data.get("briefingDateShort", get_current_date_info()["short_str"])
    success = send_kakao_memo(tokens["access_token"], msg, short_date)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
