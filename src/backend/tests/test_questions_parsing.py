from app.api.questions import QuestionResponse, parse_compound_question


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
