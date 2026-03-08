#!/usr/bin/env python3
"""
간단한 API 키 헤더 전달 테스트
면접 시작 API가 API 키를 올바르게 받고 로깅하는지 확인
"""

import requests
import json
import os

def test_header_transmission():
    """API 키 헤더 전달 및 로깅 테스트"""
    
    base_url = "http://127.0.0.1:8004"
    analysis_id = "85b50ffd-c902-4f7a-803b-790b6fd8e115"
    
    # 환경변수 기반 테스트용 API 키
    github_token = os.getenv("TEST_GITHUB_TOKEN", "")
    google_api_key = os.getenv("TEST_GOOGLE_API_KEY", "")
    analysis_token = os.getenv("TEST_ANALYSIS_TOKEN", "")
    
    print("========== API 키 헤더 전달 테스트 ==========")
    print(f"Backend URL: {base_url}")
    print(f"Analysis ID: {analysis_id}")
    print(f"GitHub Token: {'설정됨' if github_token else '미설정'}")
    print(f"Google API Key: {'설정됨' if google_api_key else '미설정'}")
    print(f"Analysis Token: {'설정됨' if analysis_token else '미설정'}")
    
    # 1. 먼저 질문을 캐시에 직접 생성 (빠른 테스트를 위해)
    print("\n1. 테스트용 질문 캐시 생성...")
    cache_url = f"{base_url}/api/v1/questions/cache/test-questions"
    test_questions = [
        {
            "id": "test-q1",
            "question": "이 프로젝트의 주요 기술 스택에 대해 설명해주세요.",
            "type": "tech_stack",
            "difficulty": "medium"
        },
        {
            "id": "test-q2", 
            "question": "코드 품질을 높이기 위한 방법들을 제시해주세요.",
            "type": "code_quality",
            "difficulty": "medium"
        }
    ]
    
    # 2. 면접 시작 요청 (중요: API 키 헤더 포함)
    print("\n2. 면접 시작 요청 - API 키 헤더 확인...")
    interview_url = f"{base_url}/api/v1/interview/start"
    interview_data = {
        "repo_url": "https://github.com/microsoft/vscode",
        "analysis_id": analysis_id,
        "question_ids": ["test-q1", "test-q2"],  # 테스트 질문 ID 사용
        "interview_type": "technical",
        "difficulty_level": "medium"
    }
    
    # API 키를 헤더에 포함
    interview_headers = {
        "Content-Type": "application/json",
        "x-github-token": github_token,
        "x-google-api-key": google_api_key,
        "x-analysis-token": analysis_token,
    }
    
    print("요청 헤더:")
    print(f"  x-github-token: {'설정됨' if github_token else '미설정'}")
    print(f"  x-google-api-key: {'설정됨' if google_api_key else '미설정'}")
    print(f"  x-analysis-token: {'설정됨' if analysis_token else '미설정'}")
    
    try:
        print("\n실제 요청 전송 중...")
        response = requests.post(
            interview_url,
            json=interview_data,
            headers=interview_headers,
            timeout=30
        )
        
        print(f"\n응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 요청 성공!")
            print(f"응답: {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            print("❌ 요청 실패")
            print(f"응답: {response.text}")
        
        print("\n📋 백엔드 로그를 확인하세요:")
        print("  - 민감 키가 평문으로 출력되지 않는지 확인")
        
    except Exception as e:
        print(f"❌ 요청 오류: {e}")

if __name__ == "__main__":
    test_header_transmission()
