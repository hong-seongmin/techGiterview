# TechGiterview 🚀

> GitHub 저장소를 분석하여 맞춤형 기술면접 질문을 생성하는 AI 플랫폼

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/hong-seongmin/techGiterview.svg)](https://github.com/hong-seongmin/techGiterview/stargazers)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-🌐%20tgv.oursophy.com-blue)](https://tgv.oursophy.com/)

## 📸 Demo Screenshots

### 🏠 홈페이지 & API 키 설정
<img src="./demo/demo1.png" width="700" alt="홈페이지">

*GitHub 저장소 URL 입력, AI 모델 선택, API 키 설정 버튼을 포함한 메인 화면*

### 📊 저장소 분석 대시보드
<div align="center">
<img src="./demo/demo2.png" width="700" alt="분석 대시보드 1">
<br><br>
<img src="./demo/demo3.png" width="700" alt="분석 대시보드 2">
</div>

*SmartFileImportanceAnalyzer 기반 저장소 분석, 기술 스택 요약, 질문/코드 그래프 및 레거시 상세 대시보드 화면*

### 💬 AI 질문 생성 & 모의면접
<img src="./demo/demo4.png" width="700" alt="질문 생성 및 모의면접">

*저장소 분석 결과를 바탕으로 생성된 맞춤형 기술면접 질문과 답변 제출 후 즉시 피드백을 제공하는 모의면접*

---

## 🌐 Live Demo

**[🚀 https://tgv.oursophy.com/](https://tgv.oursophy.com/)**

실제 서비스를 바로 체험해보세요! GitHub 저장소 URL과 AI API 키 1개(Upstage 또는 Google)만 있으면 바로 이용할 수 있습니다.

## ✨ 주요 기능

### 🔑 유연한 API 키 관리
- **개발환경**: `.env.dev` 파일 기반 설정
- **웹 UI 지원**: localStorage에 API 키를 저장하고 화면에서 바로 관리
- **요청 전달 방식**: 저장된 키는 분석/질문 생성 시 필요한 요청 헤더로 전달되며, localStorage 모드에서는 서버에 영구 저장하지 않음

### 🧠 스마트 분석 시스템
- **SmartFileImportanceAnalyzer**: 4차원 파일 중요도 분석 (복잡도, 의존성, 크기, 패턴)
- **기술 스택 자동 탐지**: 프로젝트별 맞춤 기술 스택 식별
- **복잡도 점수**: 0-10점 스케일 기반 코드 복잡도 평가

### 🤖 AI 기반 질문 생성
- **멀티 프로바이더 지원**: Upstage Solar Pro3 우선, Google Gemini 2.0 Flash 지원
- **맞춤형 질문**: 저장소 분석 결과 기반 특화 질문
- **기본 3가지 유형**: 기술스택, 아키텍처, 코드분석 질문 균형 배분
- **확장 질문 유형**: design patterns, problem solving, best practices까지 지원

### 💬 실시간 모의면접
- **기본 UI 진행 방식**: REST 기반 답변 제출 및 피드백 처리, 백엔드 WebSocket 엔드포인트 지원
- **즉시 피드백**: AI 기반 답변 분석 및 개선 제안
- **진행률 추적**: 질문별 답변 완료도 시각화

### 🎨 모던 UI/UX
- **React 18 + TypeScript**: 최신 웹 기술 스택
- **반응형 디자인**: 데스크톱/모바일 최적화
- **접근성 지원**: 키보드/ARIA 패턴 적용, 다크모드 지원

## 🚀 빠른 시작

### 방법 1: Docker Compose (권장)

```bash
# 1. 프로젝트 클론
git clone https://github.com/hong-seongmin/techGiterview.git
cd techGiterview

# 2. Docker Compose 실행
docker-compose up -d

# 3. 접속
# Frontend: http://localhost:9105
# Backend: http://localhost:9104
# API 문서: http://localhost:9104/docs
```

> 💡 **API 키 설정**: 웹 사이트 접속 후 '**API 키 설정**' 버튼을 클릭하여 AI API 키를 입력하세요. Upstage 또는 Google API 키 중 하나가 필수이며, GitHub 토큰은 선택 사항입니다. 저장한 키는 브라우저 localStorage에 보관할 수 있고, 필요한 API 요청 시 헤더로 전달됩니다.

### 방법 2: 개발 환경 설정

```bash
# 1. 프로젝트 클론
git clone https://github.com/hong-seongmin/techGiterview.git
cd techGiterview

# 2. 환경 변수 파일 생성 (개발용)
cat > src/backend/.env.dev <<'EOF'
GITHUB_TOKEN=ghp_your_optional_github_token
UPSTAGE_API_KEY=up_your_upstage_api_key
GOOGLE_API_KEY=AIza_your_google_api_key
EOF

# Upstage 또는 Google API 키 중 하나는 필수, GitHub 토큰은 선택

# 3. Docker Compose 실행
docker-compose up -d
```

### API 키 발급 가이드

> 현재 서비스는 **Upstage Solar Pro3** 와 **Google Gemini 2.0 Flash** 를 모두 지원합니다. 두 키 중 하나만 있어도 분석과 질문 생성이 가능합니다.

#### GitHub Personal Access Token
1. [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens) 접속
2. **Generate new token (classic)** 클릭
3. **repo** 권한 체크 (저장소 읽기용)
4. 생성된 `ghp_` 토큰 복사

#### Google API Key (Gemini)
1. [Google AI Studio](https://aistudio.google.com/app/apikey) 접속
2. **Create API Key** 클릭
3. 생성된 `AIza` 키 복사

## 🛠 기술 스택

### Backend
- **FastAPI** - 고성능 Python 웹 프레임워크
- **Upstage Solar Pro3 + Google Gemini 2.0 Flash** - 멀티 프로바이더 AI 구성
- **LangGraph** - AI 에이전트 워크플로우 관리
- **SmartFileImportanceAnalyzer** - 4차원 파일 중요도 분석 알고리즘
- **SQLite (기본) / PostgreSQL (호환)** - 분석 결과 및 면접 데이터 저장
- **Redis** - 일부 캐싱 및 세션/토큰 연동
- **ChromaDB** - 선택적 벡터 임베딩 저장소
- **aiohttp** - 비동기 HTTP 클라이언트 (GitHub API)

### Frontend  
- **React 18** + **TypeScript** - 모던 웹 프레임워크
- **Vite** - 차세대 빌드 도구 (HMR 지원)
- **CSS Variables** - 동적 테마 시스템 (다크모드 지원)
- **LocalStorage API** - 로컬 API 키 저장 및 세션 토큰 관리
- **REST + WebSocket** - 현재 면접 UI는 REST 중심, 백엔드 WebSocket 엔드포인트 지원
- **Responsive Design** - 모바일 최적화

### DevOps & Infrastructure
- **Docker** + **Docker Compose** - 컨테이너 기반 배포
- **SQLite + Redis** - 기본 로컬/개발 실행 스택
- **PostgreSQL** - 선택적 호환 데이터베이스
- **Redis 7** - 인메모리 캐시
- **Nginx** - 프로덕션 프론트엔드 정적 파일 서빙

## 📊 SmartFileImportanceAnalyzer - 4차원 파일 중요도 분석

TechGiterview는 **4가지 핵심 지표**로 저장소 파일의 중요도를 정량적으로 측정합니다:

### 🧮 1. 복잡도 점수 (Complexity Score) - 가중치 10%
**McCabe 순환복잡도** 기반 코드 품질 측정

```python
# 계산 공식 (file_importance_analyzer.py:685-711)
complexity_importance = (
    (cyclomatic_complexity / 20.0) * 0.4 +        # 순환복잡도 (최대 20)
    (1.0 - maintainability_index/100.0) * 0.3 +   # 유지보수성 역산
    (executable_lines / 200.0) * 0.3              # 실행 라인 수 (최대 200)
)
```

- **순환복잡도**: `if`, `for`, `while`, `try/except` 등 분기문 개수 측정
- **유지보수성**: Microsoft MI 공식 기반 (0~100, 높을수록 좋음)
- **실행 라인**: 주석/공백 제외한 실제 코드 라인 수

### 🌐 2. 의존성 중심성 (Dependency Centrality) - 가중치 30%
**NetworkX 그래프 분석** 기반 파일 간 연결 중요도

```python
# 계산 공식 (dependency_analyzer.py:623-638)  
integrated_score = (
    pagerank * 0.30 +           # PageRank: 전체적 영향력
    betweenness * 0.25 +        # Betweenness: 연결 중개자 역할
    in_degree_norm * 0.25 +     # In-degree: 피의존성 (얼마나 많이 참조되는가)
    out_degree_norm * 0.20      # Out-degree: 의존성 (얼마나 많이 참조하는가)
)
```

- **PageRank**: 웹 검색 알고리즘과 동일한 방식으로 파일의 전체적 영향력 측정
- **Betweenness**: 다른 파일들 간의 연결을 중개하는 역할 정도
- **Degree**: import/require 구문 분석으로 직접적 의존 관계 파악

### 📈 3. 변경 빈도 점수 (Git Churn Score) - 가중치 20%  
**Git 이력 분석** 기반 파일 활동도 및 안정성

```python
# 계산 공식 (file_importance_analyzer.py:655-683)
churn_importance = (
    (commit_frequency / 20.0) * 0.3 +    # 커밋 빈도 (최대 20회)
    recent_activity * 0.3 +              # 최근 활동도 (0-1)  
    stability_score * 0.4                # 안정성 점수 (0-1)
)
```

- **커밋 빈도**: 해당 파일이 포함된 총 커밋 수
- **최근 활동도**: 최근 3개월 내 활동 비율 
- **안정성**: 버그 수정 비율의 역산 (낮을수록 안정적)

### 📁 4. 메타데이터 중요도 (Metadata Score) - 가중치 40%
**구조적 특성** 기반 파일 역할 및 중요도

```python  
# 계산 공식 (file_importance_analyzer.py:1292-1297)
complexity_score = (
    code_density * 0.3 +                    # 코드 밀도 (비어있지 않은 라인 비율)
    min(1.0, keyword_density * 10) * 0.4 +  # 키워드 밀도 (함수, 클래스, 제어문)
    min(1.0, special_pattern_density * 20) * 0.2 +  # 특별 패턴 (export, API 등)
    min(1.0, documentation_ratio * 5) * 0.1  # 문서화 비율
)
```

**구조적 중요도 패턴 매칭**:
- **메인 파일 보너스**: `main.py`, `app.js`, `index.tsx`, `package.json` → 파일명 multiplier 최대 1.4
- **설정 파일 중요도**: `package.json`, `Dockerfile`, `tsconfig.json`, `vite.config.ts` 등 → 최대 1.0
- **핵심 경로 보너스**: `src/` 1.2, `core/` 1.25, `components/` / `app/` 1.15
- **테스트/문서 디스카운트**: `tests/` 0.3, `docs/` 0.4

### 🎯 최종 통합 점수 계산
```python
# 가중 평균 (file_importance_analyzer.py:576-581)
final_importance = (
    metadata_score * 0.4 +      # 40%: 구조적 중요도 (파일 역할)
    centrality_score * 0.3 +    # 30%: 의존성 중심성 (연결 중요도)  
    churn_score * 0.2 +         # 20%: 변경 빈도 (활동도)
    complexity_score * 0.1      # 10%: 복잡도 (품질 지표)
)
```

### 💡 면접 질문 생성 활용
- **선별된 핵심 파일**: 핵심 아키텍처 설계 질문
- **고복잡도 파일**: 코드 리뷰 및 리팩토링 전략
- **높은 중심성 파일**: 의존성 관리 및 모듈 설계
- **변경 이력/핫스팟 신호**: 유지보수 및 협업 프로세스 질문

---

## 🎯 사용 가이드

### 1️⃣ 저장소 분석
1. [라이브 데모](https://tgv.oursophy.com/) 접속
2. **API 키 설정** 버튼 클릭 → Upstage 또는 Google API 키 입력, 필요 시 GitHub 토큰 추가
3. GitHub 저장소 URL 입력 (예: `https://github.com/facebook/react`)
4. **분석 시작** 버튼 클릭

### 2️⃣ 분석 결과 확인
- 📊 **기술 스택 요약**: 프로젝트에서 감지된 언어/기술 비율
- 📁 **핵심 파일 및 저장소 정보**: SmartFileImportanceAnalyzer 기반 선별 결과
- 🧭 **질문/코드 그래프/레거시 상세 대시보드**: 현재 기본 대시보드는 질문과 코드 그래프 중심

### 3️⃣ AI 질문 생성 & 모의면접
- ❓ **맞춤형 질문**: 분석 결과 기반 기술면접 질문 자동 생성
- 💬 **면접 세션 진행**: 질문에 답변하고 즉시 AI 피드백 받기
- 📈 **진행률 추적**: 질문별 답변 완료도 시각화

## 🧪 개발 & 테스트

```bash
# 백엔드 테스트
cd src/backend
uv run pytest tests/ -v

# 프론트엔드 테스트
cd src/frontend  
npm test

# Docker 환경 테스트
docker-compose exec backend pytest tests/
```

## 🤝 기여하기

1. 프로젝트 Fork
2. 기능 브랜치 생성: `git checkout -b feature/amazing-feature`
3. 변경사항 커밋: `git commit -m 'Add amazing feature'`
4. 브랜치 Push: `git push origin feature/amazing-feature`
5. Pull Request 생성

## ☕ 후원

이 프로젝트가 도움이 되셨다면 커피 한 잔으로 응원해주세요!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/oursophy)

## 📄 라이선스

MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 👨‍💻 개발자

**Hong Seongmin** - [GitHub](https://github.com/hong-seongmin)

---

⭐ 이 프로젝트가 유용하다면 Star를 눌러주세요!
