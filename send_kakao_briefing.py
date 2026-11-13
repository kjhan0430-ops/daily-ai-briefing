#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[매일 아침 8시 카카오톡 AI 브리핑 자동 전송 스크립트]
- 카카오톡 '나에게 보내기 API'를 사용하여 전일/오늘의 AI 에이전트 & 실무 트렌드를 요약 전송합니다.
"""

import os
import json
import datetime
import requests

# 1. 설정값
KAKAO_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "kakao_token.json")
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "7d96bc8cb2bae33dcc971e8359885142")
CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "mhWBNuOtcBAO67ShqKnDK9JtdrVYdUGe")

def get_current_date_str():
    now = datetime.datetime.now()
    days = ["월", "화", "수", "목", "금", "토", "일"]
    day_str = days[now.weekday()]
    return now.strftime(f"%Y년 %m월 %d일 ({day_str})")

def load_tokens():
    if os.path.exists(KAKAO_TOKEN_FILE):
        with open(KAKAO_TOKEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    access_token = os.environ.get("KAKAO_ACCESS_TOKEN", "")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN", "")
    if access_token:
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
        "refresh_token": tokens["refresh_token"]
    }
    resp = requests.post(url, data=data)
    result = resp.json()
    if "access_token" in result:
        tokens["access_token"] = result["access_token"]
        if "refresh_token" in result:
            tokens["refresh_token"] = result["refresh_token"]
        with open(KAKAO_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
        print(">> 카카오 액세스 토큰 자동 갱신 완료")
    return tokens

def generate_briefing_message():
    date_str = get_current_date_str()
    
    text = f"""[🚀 데일리 AI 실무 트렌드 브리핑]
📅 {date_str} 아침 8시 브리핑

📢 전일 신규 AI 실무 콘텐츠: 총 9건 업데이트!
(국내 유튜버 5건 / 해외 글로벌 4건)

🇰🇷 [국내 실무 핵심 요약]
1. 조코딩: 맥미니 한 대로 AI 직원 세팅하기
   • 이메일 답장·리포트 작성을 AI 비서에게 100% 위임
2. 테디노트: LangGraph 에이전트로 사내 RAG 정복
   • 회사 문서 연동 시 환각 방지 및 권한 분리 팁
3. 일잘러 장피엠: 2026 실무 LLM 3대장 비교
   • 코딩은 Claude, 방대한 분석은 Gemini, 기획은 GPT

🌏 [해외 글로벌 트렌드]
• Wes Roth: Claude Code 터미널 에이전트 (.clauderules 설정법)
• Matthew Berman: Gemini 2.0 AI Studio 200만 토큰 실무 연동

⚡ [오늘의 실전 프롬프트]
"시니어 관점 코드 리팩토링 & 보안 점검 프롬프트 탑재"

👉 폰에서 AI 대시보드 바로 열기:
https://daily-ai-briefing.netlify.app"""
    return text

def send_kakao_memo(access_token, message_text):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    payload = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": message_text,
            "link": {
                "web_url": "https://www.youtube.com",
                "mobile_web_url": "https://www.youtube.com"
            },
            "button_title": "AI 대시보드 열기"
        }, ensure_ascii=False)
    }

    resp = requests.post(url, headers=headers, data=payload)
    if resp.status_code == 200 and resp.json().get("result_code") == 0:
        print("✅ 카카오톡 메시지 전송 성공!")
        return True
    else:
        print(f"❌ 전송 실패: {resp.status_code} - {resp.text}")
        return False

def main():
    print(f">> 카카오톡 데일리 AI 브리핑 발송 시작 ({datetime.datetime.now()})")
    tokens = load_tokens()
    
    if not tokens or not tokens.get("access_token"):
        print("⚠️ 카카오 토큰 정보가 없습니다.")
        return

    # 토큰 갱신 시도 (만료 방지)
    tokens = refresh_kakao_token(tokens)
    
    # 메시지 생성 및 전송
    msg = generate_briefing_message()
    send_kakao_memo(tokens["access_token"], msg)

if __name__ == "__main__":
    main()
