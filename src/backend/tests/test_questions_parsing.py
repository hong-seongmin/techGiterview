import uuid

from app.api.questions import QuestionResponse, ensure_unique_question_ids, parse_compound_question


def test_parse_compound_question_removes_markdown_sections():
    question = QuestionResponse(
        id="q1",
        type="code_analysis",
        difficulty="medium",
        question="""### 기술면접 질문

**질문:** `packages/vite/src/node/index.ts` 파일의 구조와 주요 기능을 설명해주세요.
**파일 경로:** `packages/vite/src/node/index.ts`
**참조 코드:**
```ts
export async function createServer() {}
```
**근거:** 실제 createServer 함수가 존재합니다.
""",
    )

    parsed = parse_compound_question(question)

    assert len(parsed) == 1
    assert parsed[0].question == "`packages/vite/src/node/index.ts` 파일의 구조와 주요 기능을 설명해주세요."


def test_parse_compound_question_removes_question_label_only():
    question = QuestionResponse(
        id="q2",
        type="tech_stack",
        difficulty="medium",
        question="**질문:** packages/vite/src/node/index.ts에서 드러나는 Node.js 사용 방식을 설명해주세요.",
    )

    parsed = parse_compound_question(question)

    assert len(parsed) == 1
    assert parsed[0].question == "packages/vite/src/node/index.ts에서 드러나는 Node.js 사용 방식을 설명해주세요."


def test_parse_compound_question_removes_dangling_choice_prefix_without_options():
    question = QuestionResponse(
        id="q3",
        type="architecture",
        difficulty="medium",
        question="다음 중 main.go, go.mod 기준으로 런타임 핵심 모듈과 초기화 책임이 어떻게 분리되는지 설명해주세요.",
    )

    parsed = parse_compound_question(question)

    assert len(parsed) == 1
    assert parsed[0].question == "main.go, go.mod 기준으로 런타임 핵심 모듈과 초기화 책임이 어떻게 분리되는지 설명해주세요."


def test_parse_compound_question_keeps_choice_prefix_when_options_exist():
    question = QuestionResponse(
        id="q4",
        type="architecture",
        difficulty="medium",
        question="다음 중 어떤 설명이 맞나요? 1. 요청 라우팅 2. 빌드 파이프라인",
    )

    parsed = parse_compound_question(question)

    assert len(parsed) == 1
    assert parsed[0].question == "다음 중 어떤 설명이 맞나요? 1. 요청 라우팅 2. 빌드 파이프라인"


def test_parse_compound_question_removes_generator_prologue_and_dangling_quote():
    question = QuestionResponse(
        id="q5",
        type="code_analysis",
        difficulty="medium",
        question='다음은 실제 package.json 파일의 내용을 직접 참조하여 생성한 기술면접 질문입니다: "이 package.json에서 router 의존성 패키지가 명시적으로 선언되지 않은 이유는 무엇이라고 생각하시나요?',
    )

    parsed = parse_compound_question(question)

    assert len(parsed) == 1
    assert parsed[0].question == "이 package.json에서 router 의존성 패키지가 명시적으로 선언되지 않은 이유는 무엇이라고 생각하시나요?"


def test_ensure_unique_question_ids_rewrites_all_ids_as_global_uuids():
    questions = [
        QuestionResponse(
            id="architecture_1234",
            type="architecture",
            difficulty="medium",
            question="첫 번째 질문",
        ),
        QuestionResponse(
            id="architecture_1234",
            type="architecture",
            difficulty="medium",
            question="두 번째 질문",
        ),
    ]

    normalized = ensure_unique_question_ids(questions)

    assert len(normalized) == 2
    assert normalized[0].id != normalized[1].id
    uuid.UUID(normalized[0].id)
    uuid.UUID(normalized[1].id)


def test_ensure_unique_question_ids_rewrites_parent_links():
    questions = [
        QuestionResponse(
            id="parent_question",
            type="architecture",
            difficulty="medium",
            question="부모 질문",
        ),
        QuestionResponse(
            id="child_question",
            type="architecture",
            difficulty="medium",
            question="자식 질문",
            parent_question_id="parent_question",
            is_compound_question=True,
        ),
    ]

    normalized = ensure_unique_question_ids(questions)

    assert len(normalized) == 2
    assert normalized[1].parent_question_id == normalized[0].id
    uuid.UUID(normalized[0].id)
    uuid.UUID(normalized[1].id)
