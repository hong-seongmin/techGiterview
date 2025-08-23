"""
Question Generator Agent

GitHub 저장소 분석 결과를 바탕으로 기술면접 질문을 생성하는 LangGraph 에이전트
"""

import json
import random
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# from langgraph.graph import StateGraph, END
# from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.ai_service import ai_service, AIProvider
from app.core.gemini_client import get_gemini_llm
# from app.services.vector_db import VectorDBService


@dataclass
class QuestionState:
    """질문 생성 상태를 관리하는 데이터 클래스"""
    repo_url: str
    analysis_data: Optional[Dict[str, Any]] = None
    code_snippets: Optional[List[Dict[str, Any]]] = None
    questions: Optional[List[Dict[str, Any]]] = None
    difficulty_level: str = "medium"  # easy, medium, hard
    question_types: Optional[List[str]] = None
    error: Optional[str] = None


class QuestionGenerator:
    """기술면접 질문 생성 에이전트"""
    
    def __init__(self):
        # self.vector_db = VectorDBService()
        
        # Google Gemini LLM 초기화
        self.llm = get_gemini_llm()
        self.ai_service = ai_service
        
        if self.llm:
            # Gemini에 맞는 설정 조정
            self.llm.temperature = 0.7  # 창의적인 질문 생성을 위해
            print("[QUESTION_GENERATOR] Google Gemini LLM initialized successfully")
        else:
            print("[QUESTION_GENERATOR] Warning: Gemini LLM not available, using template-based generation")
        
        # 더미 템플릿 제거 - 실제 파일 내용만으로 질문 생성
        
        # 난이도별 복잡도 범위
        self.complexity_ranges = {
            "easy": (1.0, 3.0),
            "medium": (3.0, 6.0), 
            "hard": (6.0, 10.0)
        }
    
    async def generate_questions(
        self, 
        repo_url: str, 
        difficulty_level: str = "medium",
        question_count: int = 9,
        question_types: Optional[List[str]] = None,
        analysis_data: Optional[Dict[str, Any]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """기술면접 질문 생성"""
        
        # API 키를 인스턴스 변수로 저장
        self.api_keys = api_keys or {}
        
        # 상태 초기화
        state = QuestionState(
            repo_url=repo_url,
            difficulty_level=difficulty_level,
            question_types=question_types or ["tech_stack", "architecture", "code_analysis"]  # 3가지 질문 타입 균등 분배
        )
        
        try:
            # 1. 분석 데이터 설정
            if analysis_data:
                # 직접 전달받은 분석 데이터 사용
                import json
                state.analysis_data = {
                    "metadata": {
                        "tech_stack": json.dumps(analysis_data.get("tech_stack", {})),
                        "complexity_score": analysis_data.get("complexity_score", 0.0),
                        "file_count": len(analysis_data.get("key_files", [])),
                        "repo_info": analysis_data.get("repo_info", {})
                    },
                    "analysis_text": analysis_data.get("summary", "")
                }
            else:
                # 분석 데이터가 없으면 에러 반환
                raise ValueError(f"저장소 분석 데이터가 제공되지 않았습니다: {repo_url}. 먼저 저장소를 분석해주세요.")
            
            # 2. 관련 코드 스니펫 조회 (key_files 우선 활용)
            state.code_snippets = []
            if analysis_data and "key_files" in analysis_data:
                print(f"[DEBUG] key_files 개수: {len(analysis_data['key_files'])}")
                # 분석 데이터에서 파일 정보 활용
                for file_info in analysis_data["key_files"][:8]:  # 최대 8개로 증가
                    file_path = file_info.get("path", "unknown")
                    file_content = file_info.get("content", "# File content not available")
                    
                    # 파일 확장자에 따른 언어 추론
                    language = self._infer_language_from_path(file_path)
                    
                    # 파일 내용이 실제로 존재하는지 확인 (더욱 관대한 검사)
                    has_real_content = (
                        file_content and 
                        file_content != "null" and
                        file_content.strip() != "" and
                        len(file_content.strip()) > 10 and  # 최소 10자 이상으로 대폭 완화
                        not file_content.startswith("# File content not available") and
                        not file_content.strip() == "File content not available"
                    )
                    
                    # 추가 검사: 설정 파일이나 문서 파일은 더욱 관대하게 처리
                    file_ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
                    is_config_or_doc = file_ext in ['json', 'yml', 'yaml', 'toml', 'md', 'rst', 'txt', 'cfg', 'ini']
                    
                    if is_config_or_doc and file_content and len(file_content.strip()) > 5:
                        has_real_content = True  # 설정/문서 파일은 5자 이상이면 유효
                    
                    print(f"[DEBUG] 파일 내용 검사: {file_path}")
                    print(f"  - 내용 길이: {len(file_content) if file_content else 0}")
                    print(f"  - has_real_content: {has_real_content}")
                    if not has_real_content and file_content:
                        print(f"  - 내용 미리보기: {file_content[:100]}...")
                    
                    # 파일 유형별 중요도 자동 설정
                    file_importance = self._determine_file_importance(file_path, file_content)
                    
                    snippet_data = {
                        "id": file_path,
                        "content": file_content,
                        "metadata": {
                            "language": language,
                            "file_path": file_path,
                            "complexity": self._estimate_code_complexity(file_content) if has_real_content else 1.0,
                            "has_real_content": has_real_content,
                            "content_unavailable_reason": file_info.get("content_unavailable_reason"),
                            "importance": file_importance,
                            "file_type": self._categorize_file_type(file_path),
                            "extracted_elements": self._extract_code_elements(file_content, language) if has_real_content else {}
                        }
                    }
                    
                    state.code_snippets.append(snippet_data)
                    print(f"[DEBUG] 파일: {file_path}, 실제 내용: {has_real_content}, 중요도: {file_importance}")
            else:
                print(f"[DEBUG] key_files 없음. analysis_data 키들: {list(analysis_data.keys()) if analysis_data else 'None'}")
            
            # 3. 질문 생성 - 전체 파일 현황 로그 추가
            print(f"[QUESTION_GEN] ========== 질문 생성 시작 - 전체 현황 ==========")
            print(f"[QUESTION_GEN] 요청된 질문 개수: {question_count}")
            print(f"[QUESTION_GEN] 질문 타입: {state.question_types}")
            print(f"[QUESTION_GEN] 전체 파일 수: {len(state.code_snippets) if state.code_snippets else 0}")
            if state.code_snippets:
                real_content_count = sum(1 for s in state.code_snippets if s["metadata"].get("has_real_content", False))
                print(f"[QUESTION_GEN] 실제 내용이 있는 파일 수: {real_content_count}")
                print(f"[QUESTION_GEN] 파일별 상세 현황:")
                for i, snippet in enumerate(state.code_snippets[:10]):  # 최대 10개만 표시
                    file_path = snippet["metadata"].get("file_path", "unknown")
                    has_content = snippet["metadata"].get("has_real_content", False)
                    content_len = len(snippet["content"]) if snippet["content"] else 0
                    importance = snippet["metadata"].get("importance", "unknown")
                    print(f"[QUESTION_GEN]   {i+1}. {file_path} - 실제내용: {has_content} - 길이: {content_len} - 중요도: {importance}")
            print(f"[QUESTION_GEN] ========================================")
            
            state.questions = await self._generate_questions_by_type(state, question_count)
            
            # 질문 생성 완료 로그
            print(f"[QUESTION_GEN] ========== 질문 생성 최종 결과 ==========")
            print(f"[QUESTION_GEN] 생성된 총 질문 수: {len(state.questions)}")
            if state.questions:
                for i, q in enumerate(state.questions):
                    q_type = q.get("type", "unknown")
                    q_preview = q.get("question", "")[:100] + "..." if len(q.get("question", "")) > 100 else q.get("question", "")
                    source_file = q.get("source_file", q.get("context", "unknown"))
                    print(f"[QUESTION_GEN]   {i+1}. [{q_type}] {q_preview} (출처: {source_file})")
            print(f"[QUESTION_GEN] ==========================================")
            
            # 4. 결과 반환
            return {
                "success": True,
                "repo_url": repo_url,
                "difficulty": difficulty_level,
                "question_count": len(state.questions),
                "questions": state.questions,
                "analysis_context": self._extract_context_summary(state.analysis_data),
                "code_snippets_count": len(state.code_snippets) if state.code_snippets else 0
            }
            
        except Exception as e:
            state.error = str(e)
            return {
                "success": False,
                "error": state.error,
                "repo_url": repo_url,
                "questions": []
            }
    
    async def _get_relevant_code_snippets(self, state: QuestionState) -> List[Dict[str, Any]]:
        """관련 코드 스니펫 조회"""
        
        snippets = []
        
        # 난이도에 따른 복잡도 범위 설정
        min_complexity, max_complexity = self.complexity_ranges[state.difficulty_level]
        
        # 복잡도 기반 코드 조회
        complexity_snippets = await self.vector_db.get_code_by_complexity(
            min_complexity=min_complexity,
            max_complexity=max_complexity,
            limit=5
        )
        snippets.extend(complexity_snippets)
        
        # 기술 스택 기반 코드 검색
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_stack = json.loads(tech_stack_str)
                for tech in list(tech_stack.keys())[:3]:  # 주요 기술 3개
                    tech_snippets = await self.vector_db.search_similar_code(
                        query=tech,
                        limit=2
                    )
                    snippets.extend(tech_snippets)
            except:
                pass
        
        # 중복 제거
        seen_ids = set()
        unique_snippets = []
        for snippet in snippets:
            if snippet["id"] not in seen_ids:
                seen_ids.add(snippet["id"])
                unique_snippets.append(snippet)
        
        return unique_snippets[:8]  # 최대 8개 스니펫
    
    async def _generate_questions_by_type(self, state: QuestionState, question_count: int) -> List[Dict[str, Any]]:
        """타입별 질문 생성 - 균등 분배"""
        
        print(f"[QUESTION_GEN] ========== 타입별 질문 생성 프로세스 시작 ==========")
        print(f"[QUESTION_GEN] 총 요청 질문 개수: {question_count}")
        print(f"[QUESTION_GEN] 질문 타입들: {state.question_types}")
        
        questions = []
        questions_per_type = question_count // len(state.question_types)  # 3가지 타입이면 각 3개씩
        remaining_questions = question_count % len(state.question_types)
        
        print(f"[QUESTION_GEN] 질문 분배 계획:")
        print(f"[QUESTION_GEN]   - 기본 타입당: {questions_per_type}개")
        print(f"[QUESTION_GEN]   - 나머지 질문: {remaining_questions}개 (첫 번째 타입들에 추가)")
        
        type_generation_results = {}
        
        # 각 타입별로 정확히 지정된 수만큼 생성
        for i, question_type in enumerate(state.question_types):
            # 나머지 질문은 첫 번째 타입들에 1개씩 추가
            current_count = questions_per_type + (1 if i < remaining_questions else 0)
            
            print(f"[QUESTION_GEN] ========== {question_type} 타입 처리 시작 ==========")
            print(f"[QUESTION_GEN] 할당된 질문 개수: {current_count}개 ({questions_per_type} + {1 if i < remaining_questions else 0})")
            
            try:
                type_questions = await self._generate_questions_for_type(state, question_type, current_count)
                questions.extend(type_questions)
                
                # 결과 기록
                type_generation_results[question_type] = {
                    "requested": current_count,
                    "generated": len(type_questions),
                    "success_rate": len(type_questions) / current_count if current_count > 0 else 0
                }
                
                print(f"[QUESTION_GEN] {question_type} 타입 완료: {len(type_questions)}/{current_count}개 생성")
                
            except Exception as e:
                error_msg = f"{question_type} 타입 전체 생성 실패: {str(e)}"
                print(f"[QUESTION_GEN] ERROR: {error_msg}")
                
                type_generation_results[question_type] = {
                    "requested": current_count,
                    "generated": 0,
                    "success_rate": 0,
                    "error": error_msg
                }
        
        # 최종 결과 요약
        total_generated = len(questions)
        overall_success_rate = total_generated / question_count if question_count > 0 else 0
        
        print(f"[QUESTION_GEN] ========== 타입별 질문 생성 최종 결과 ==========")
        print(f"[QUESTION_GEN] 전체 결과: {total_generated}/{question_count}개 생성 (성공률: {overall_success_rate:.1%})")
        print(f"[QUESTION_GEN] 타입별 상세 결과:")
        
        for question_type, result in type_generation_results.items():
            status = "✅" if result["success_rate"] >= 0.8 else "⚠️" if result["success_rate"] >= 0.5 else "❌"
            print(f"[QUESTION_GEN]   {status} {question_type}: {result['generated']}/{result['requested']}개 ({result['success_rate']:.1%})")
            
            if "error" in result:
                print(f"[QUESTION_GEN]     오류: {result['error']}")
        
        # 성공률이 낮은 경우 경고
        if overall_success_rate < 0.7:
            print(f"[QUESTION_GEN] WARNING: 전체 질문 생성 성공률이 낮습니다 ({overall_success_rate:.1%})")
            print(f"[QUESTION_GEN] 부족한 질문을 템플릿 기반으로 보완합니다.")
        
        # 목표 개수에 못 미치는 경우 추가 질문 생성
        if total_generated < question_count:
            missing_count = question_count - total_generated
            print(f"[QUESTION_GEN] 부족한 질문 {missing_count}개를 보완합니다.")
            
            # 실패한 타입들을 우선으로 템플릿 기반 질문 추가
            failed_types = [qtype for qtype, result in type_generation_results.items() 
                           if result["generated"] < result["requested"]]
            
            if failed_types:
                print(f"[QUESTION_GEN] 실패한 타입들을 우선 보완: {failed_types}")
                additional_questions = await self._generate_template_questions(state, failed_types, missing_count)
                questions.extend(additional_questions)
                print(f"[QUESTION_GEN] 템플릿 기반 질문 {len(additional_questions)}개 추가")
            
            # 여전히 부족하면 일반 템플릿 질문 추가
            if len(questions) < question_count:
                remaining = question_count - len(questions)
                general_questions = await self._generate_general_template_questions(state, remaining)
                questions.extend(general_questions)
                print(f"[QUESTION_GEN] 일반 템플릿 질문 {len(general_questions)}개 추가")
        
        print(f"[QUESTION_GEN] =============================================")
        
        # 목표 개수에 맞춰 자르기 (혹시 초과 생성된 경우)
        final_questions = questions[:question_count]
        final_count = len(final_questions)
        
        print(f"[QUESTION_GEN] 최종 결과: {final_count}/{question_count}개 질문 확보")
        
        # 최종 성공률 계산
        final_success_rate = final_count / question_count if question_count > 0 else 0
        if final_success_rate >= 0.9:
            print(f"[QUESTION_GEN] ✅ 목표 달성: {final_success_rate:.1%} 성공률")
        elif final_success_rate >= 0.7:
            print(f"[QUESTION_GEN] ⚠️ 부분 성공: {final_success_rate:.1%} 성공률")
        else:
            print(f"[QUESTION_GEN] ❌ 목표 미달: {final_success_rate:.1%} 성공률")
        
        return final_questions
    
    def _get_files_for_question_index(self, all_snippets: List[Dict], question_index: int) -> List[Dict]:
        """질문 인덱스에 따라 다른 파일 세트 반환 - 순환 선택으로 다양성 확보"""
        
        print(f"[QUESTION_GEN] 파일 선택 다양성 로직 시작 - 질문 {question_index + 1}번")
        
        if not all_snippets:
            print(f"[QUESTION_GEN] 경고: 사용 가능한 파일이 없습니다.")
            return []
        
        # 파일 타입별로 그룹화
        file_groups = {}
        for snippet in all_snippets:
            file_path = snippet["metadata"].get("file_path", "").lower()
            
            # 더 세밀한 파일 타입 분류
            if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                if 'config' in file_path or 'babel' in file_path:
                    file_type = 'build_config'
                elif 'test' in file_path or 'spec' in file_path:
                    file_type = 'test'
                else:
                    file_type = 'javascript'
            elif file_path.endswith(('.py', '.pyi')):
                if 'test' in file_path:
                    file_type = 'test'
                else:
                    file_type = 'python'
            elif file_path.endswith(('.json', '.yml', '.yaml', '.toml')):
                file_type = 'config'
            elif file_path.endswith(('.md', '.rst', '.txt')):
                file_type = 'documentation'
            elif file_path.endswith(('.html', '.css', '.scss')):
                file_type = 'frontend'
            else:
                file_type = 'general'
                
            if file_type not in file_groups:
                file_groups[file_type] = []
            file_groups[file_type].append(snippet)
        
        print(f"[QUESTION_GEN] 파일 그룹화 완료: {list(file_groups.keys())}")
        for group, files in file_groups.items():
            print(f"[QUESTION_GEN]   - {group}: {len(files)}개")
        
        # 순환 선택: 파일 인덱스를 순환하여 선택 (다양성 확보)
        total_files = len(all_snippets)
        if total_files == 0:
            return []
            
        # 우선순위 타입 정의 (질문 인덱스별로)
        priority_types_list = [
            ['config', 'build_config', 'python', 'javascript', 'documentation'],  # 1번 질문
            ['python', 'javascript', 'frontend', 'build_config', 'config'],       # 2번 질문  
            ['documentation', 'test', 'frontend', 'general', 'config'],           # 3번 질문
            ['javascript', 'python', 'test', 'build_config', 'general'],          # 4번 질문
            ['frontend', 'config', 'documentation', 'python', 'javascript'],     # 5번 질문
            ['test', 'general', 'build_config', 'documentation', 'frontend'],    # 6번 질문
            ['general', 'python', 'config', 'test', 'javascript'],               # 7번 질문
            ['build_config', 'frontend', 'documentation', 'general', 'python'],  # 8번 질문
            ['config', 'test', 'javascript', 'frontend', 'documentation']        # 9번 질문
        ]
        
        # 질문 인덱스에 맞는 우선순위 타입 선택 (순환)
        priority_types = priority_types_list[question_index % len(priority_types_list)]
        print(f"[QUESTION_GEN] {question_index + 1}번 질문 - 우선순위 타입: {priority_types}")
        
        # 선택된 파일을 저장할 리스트
        selected_file = None
        
        # 1. 우선순위 타입에서 해당 인덱스의 파일 선택
        for file_type in priority_types:
            if file_type in file_groups and file_groups[file_type]:
                group_files = file_groups[file_type]
                # 중요도와 복잡도로 정렬
                group_files.sort(key=lambda f: (
                    {'very_high': 4, 'high': 3, 'medium': 2, 'low': 1}.get(f["metadata"].get("importance", "low"), 1),
                    f["metadata"].get("complexity", 1.0)
                ), reverse=True)
                
                # 해당 타입에서 순환 선택
                file_index = question_index % len(group_files)
                selected_file = group_files[file_index]
                print(f"[QUESTION_GEN]   우선순위 선택: {selected_file['metadata'].get('file_path')} ({file_type}, 인덱스: {file_index})")
                break
        
        # 2. 우선순위 타입에서 선택되지 않은 경우 전체에서 순환 선택
        if not selected_file:
            # 전체 파일에서 순환 선택
            sorted_files = sorted(all_snippets, key=lambda f: (
                {'very_high': 4, 'high': 3, 'medium': 2, 'low': 1}.get(f["metadata"].get("importance", "low"), 1),
                f["metadata"].get("complexity", 1.0)
            ), reverse=True)
            
            file_index = question_index % len(sorted_files)
            selected_file = sorted_files[file_index]
            print(f"[QUESTION_GEN]   전체에서 순환 선택: {selected_file['metadata'].get('file_path')} (인덱스: {file_index})")
        
        # 최종 선택된 파일 로깅
        if selected_file:
            file_path = selected_file["metadata"].get("file_path", "unknown")
            importance = selected_file["metadata"].get("importance", "unknown")
            has_content = selected_file["metadata"].get("has_real_content", False)
            print(f"[QUESTION_GEN] 최종 선택된 파일: {file_path} (중요도: {importance}, 실제내용: {has_content})")
            return [selected_file]
        else:
            print(f"[QUESTION_GEN] 경고: 선택된 파일이 없습니다.")
            return []
    
    def _select_diverse_files(self, available_files: List[Dict]) -> List[Dict]:
        """파일 유형 다양성을 고려한 파일 선택"""
        import random
        
        # 파일 경로 기반으로 더 정확한 유형 분류
        file_groups = {}
        for snippet in available_files:
            file_path = snippet["metadata"].get("file_path", "")
            
            # 파일 확장자와 경로로 세밀한 유형 분류
            if 'babel' in file_path.lower() or 'webpack' in file_path.lower():
                group = 'build_config'  # 빌드 설정 파일 우선순위 높임
            elif file_path.endswith(('.js', '.jsx')):
                group = 'javascript'
            elif file_path.endswith(('.ts', '.tsx')):
                group = 'typescript'
            elif file_path.endswith('.py'):
                group = 'python'
            elif file_path.endswith(('.json', '.yaml', '.yml')):
                group = 'config'
            elif file_path.endswith('.md'):
                group = 'docs'
            elif 'test' in file_path.lower():
                group = 'test'
            else:
                # 기존 file_type도 고려
                group = snippet["metadata"].get("file_type", "general")
            
            if group not in file_groups:
                file_groups[group] = []
            file_groups[group].append(snippet)
        
        # 그룹별 우선순위 설정 (빌드 설정 파일 등 중요한 설정 파일 우선)
        priority_groups = ['build_config', 'config', 'javascript', 'typescript', 'python', 'docs', 'test', 'general']
        
        selected = []
        for group in priority_groups:
            if group in file_groups:
                files = file_groups[group]
                # 중요도 순으로 정렬
                files.sort(key=lambda f: f["metadata"].get("importance", "low"), reverse=True)
                
                # 그룹별로 선택할 파일 수 조정
                select_count = 2 if group in ['build_config', 'config'] else 1
                type_selection = files[:select_count] if len(files) <= select_count else random.sample(files, select_count)
                selected.extend(type_selection)
                
                if len(selected) >= 5:  # 최대 5개까지
                    break
        
        return selected[:5]

    async def _generate_code_analysis_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 코드 분석 질문 생성"""
        
        if not state.code_snippets:
            print("[QUESTION_GEN] 코드 스니펫이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        # 우선순위 기준으로 정렬된 전체 파일 목록
        def get_priority_score(snippet):
            importance_scores = {"very_high": 100, "high": 80, "medium": 50, "low": 20}
            base_score = importance_scores.get(snippet["metadata"].get("importance", "low"), 20)
            if snippet["metadata"].get("has_real_content", False):
                base_score += 30
            complexity = snippet["metadata"].get("complexity", 1.0)
            base_score += min(complexity * 2, 10)
            return base_score
        
        all_snippets = sorted(state.code_snippets, key=get_priority_score, reverse=True)
        real_content_snippets = [s for s in all_snippets if s["metadata"].get("has_real_content", False)]
        
        if not real_content_snippets:
            print("[QUESTION_GEN] 실제 파일 내용이 없습니다. 메타데이터 기반 질문을 생성합니다.")
            # 실제 내용이 없더라도 파일명과 메타데이터 기반으로 질문 생성
            return await self._generate_metadata_based_questions(state, all_snippets, count)
        
        # 질문 인덱스에 따라 다른 파일 세트 선택
        selected_files = self._get_files_for_question_index(real_content_snippets, question_index)
        
        questions = []
        for snippet in selected_files[:count]:  # count만큼만 생성
            try:
                # 기존 질문 생성 로직 사용
                question = await self._generate_single_code_analysis_question(snippet, state)
                if question:
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 코드 분석 질문 생성 실패: {e}")
                continue
        
        return questions
    
    async def _generate_tech_stack_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 기술 스택 질문 생성"""
        
        # 기술 스택 추출
        tech_stack = []
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_stack_dict = json.loads(tech_stack_str)
                tech_stack = [tech for tech, score in tech_stack_dict.items() if score >= 0.05]
            except Exception as e:
                print(f"[QUESTION_GEN] tech_stack JSON 파싱 실패: {e}")
        
        if not tech_stack:
            print("[QUESTION_GEN] 유효한 기술 스택이 없어서 tech_stack 질문 생성을 건너뜁니다.")
            return []
        
        # 질문 인덱스에 따라 다른 파일 세트 선택
        if state.code_snippets:
            all_snippets = sorted(state.code_snippets, key=lambda s: s["metadata"].get("importance", "low"), reverse=True)
            selected_files = self._get_files_for_question_index(all_snippets, question_index)
        else:
            selected_files = []
        
        questions = []
        for i in range(count):
            tech = random.choice(tech_stack)
            
            # 선택된 파일들을 기반으로 기술 스택 질문 생성
            file_context = ""
            if selected_files:
                file_info = []
                for snippet in selected_files[:3]:  # 최대 3개 파일
                    file_path = snippet["metadata"].get("file_path", "")
                    content_preview = snippet["content"][:300]
                    file_info.append(f"파일: {file_path}\n내용: {content_preview}...")
                file_context = "\n\n".join(file_info)
            
            try:
                question = await self._generate_single_tech_stack_question(tech, file_context, state)
                if question:
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 기술 스택 질문 생성 실패: {e}")
                continue
        
        return questions
    
    async def _generate_architecture_questions_with_files(self, state: QuestionState, count: int, question_index: int) -> List[Dict[str, Any]]:
        """파일 선택 다양성을 고려한 아키텍처 질문 생성"""
        
        if not state.code_snippets:
            print("[QUESTION_GEN] 코드 스니펫이 없어서 아키텍처 질문 생성을 건너뜁니다.")
            return []
        
        # 질문 인덱스에 따라 다른 파일 세트 선택
        all_snippets = sorted(state.code_snippets, key=lambda s: s["metadata"].get("importance", "low"), reverse=True)
        selected_files = self._get_files_for_question_index(all_snippets, question_index)
        
        questions = []
        for i in range(count):
            try:
                # 선택된 파일들을 기반으로 아키텍처 분석
                architecture_context = self._analyze_architecture_patterns(selected_files)
                question = await self._generate_single_architecture_question(architecture_context, state)
                if question:
                    questions.append(question)
            except Exception as e:
                print(f"[QUESTION_GEN] 아키텍처 질문 생성 실패: {e}")
                continue
        
        return questions

    async def _generate_questions_for_type(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """특정 타입의 질문 생성 - 질문 개수 보장 및 fallback 메커니즘"""
        
        print(f"[QUESTION_GEN] ========== {question_type} 타입 질문 생성 시작 ==========")
        print(f"[QUESTION_GEN] 요청된 질문 개수: {count}")
        
        questions = []
        generation_errors = []
        max_attempts = count * 2  # 최대 시도 횟수 (요청 개수의 2배)
        
        # 각 질문마다 다른 파일 세트를 사용하여 생성
        for i in range(max_attempts):
            if len(questions) >= count:  # 목표 개수에 도달하면 종료
                break
                
            question_index = i  # 순환하며 다양한 파일 선택
            print(f"[QUESTION_GEN] {question_type} - {i+1}번째 시도 (목표: {len(questions)+1}/{count})")
            
            try:
                question_list = []
                
                if question_type == "code_analysis":
                    question_list = await self._generate_code_analysis_questions_with_files(state, 1, question_index)
                elif question_type == "tech_stack":
                    question_list = await self._generate_tech_stack_questions_with_files(state, 1, question_index)
                elif question_type == "architecture":
                    question_list = await self._generate_architecture_questions_with_files(state, 1, question_index)
                elif question_type == "design_patterns":
                    question_list = await self._generate_design_pattern_questions(state, 1)
                elif question_type == "problem_solving":
                    question_list = await self._generate_problem_solving_questions(state, 1)
                elif question_type == "best_practices":
                    question_list = await self._generate_best_practice_questions(state, 1)
                else:
                    print(f"[QUESTION_GEN] 경고: 지원되지 않는 질문 타입 {question_type}")
                    # 지원되지 않는 타입의 경우 fallback 질문 생성
                    question_list = await self._generate_fallback_questions(state, question_type, 1, question_index)
                
                if question_list:
                    questions.extend(question_list)
                    print(f"[QUESTION_GEN] {question_type} - {i+1}번째 질문 생성 성공: {len(question_list)}개 (현재 총 {len(questions)}개)")
                else:
                    error_msg = f"{question_type} - {i+1}번째 질문 생성 실패: 빈 결과 반환"
                    print(f"[QUESTION_GEN] {error_msg}")
                    generation_errors.append(error_msg)
                    
                    # 실패 시 fallback 질문 생성 시도
                    print(f"[QUESTION_GEN] fallback 질문 생성 시도...")
                    fallback_questions = await self._generate_fallback_questions(state, question_type, 1, question_index)
                    if fallback_questions:
                        questions.extend(fallback_questions)
                        print(f"[QUESTION_GEN] fallback 질문 생성 성공: {len(fallback_questions)}개")
                    
            except Exception as e:
                error_msg = f"{question_type} - {i+1}번째 질문 생성 실패: {str(e)}"
                print(f"[QUESTION_GEN] ERROR: {error_msg}")
                generation_errors.append(error_msg)
                
                # 예외 발생 시에도 fallback 질문 생성 시도
                try:
                    print(f"[QUESTION_GEN] 예외 발생, fallback 질문 생성 시도...")
                    fallback_questions = await self._generate_fallback_questions(state, question_type, 1, question_index)
                    if fallback_questions:
                        questions.extend(fallback_questions)
                        print(f"[QUESTION_GEN] 예외 처리용 fallback 질문 생성 성공: {len(fallback_questions)}개")
                except Exception as fallback_error:
                    print(f"[QUESTION_GEN] fallback 질문 생성도 실패: {fallback_error}")
                    
                continue
        
        # 목표 개수에 미달하는 경우 추가 보정
        if len(questions) < count:
            shortage = count - len(questions)
            print(f"[QUESTION_GEN] 목표 미달: {len(questions)}/{count}개. {shortage}개 추가 생성 시도...")
            
            # 간단한 템플릿 기반 질문 생성으로 부족분 보완
            template_questions = await self._generate_template_questions(state, question_type, shortage)
            questions.extend(template_questions)
            print(f"[QUESTION_GEN] 템플릿 기반 질문 {len(template_questions)}개 추가")
        
        # 생성 결과 요약
        success_count = len(questions)
        final_count = min(success_count, count)  # 최대 요청 개수까지만
        
        print(f"[QUESTION_GEN] ========== {question_type} 타입 질문 생성 결과 ==========")
        print(f"[QUESTION_GEN] 최종 생성: {final_count}개 / 요청: {count}개")
        print(f"[QUESTION_GEN] 성공률: {(final_count/count)*100:.1f}%")
        
        if generation_errors:
            print(f"[QUESTION_GEN] 발생한 오류 {len(generation_errors)}개:")
            for error in generation_errors[-3:]:  # 최근 3개만 출력
                print(f"[QUESTION_GEN]   - {error}")
        
        print(f"[QUESTION_GEN] ==============================================")
        
        return questions[:count]  # 요청한 개수만큼만 반환
    
    async def _generate_code_analysis_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """코드 분석 질문 생성 - 실제 파일 내용이 있는 경우만"""
        
        questions = []
        
        if not state.code_snippets:
            print("[DEBUG] 코드 스니펫이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        # 중요도와 내용 유무를 기준으로 우선순위 정렬
        def get_priority_score(snippet):
            importance_scores = {
                "very_high": 100,
                "high": 80,
                "medium": 50,
                "low": 20
            }
            
            base_score = importance_scores.get(snippet["metadata"].get("importance", "low"), 20)
            
            # 실제 내용이 있으면 +30점
            if snippet["metadata"].get("has_real_content", False):
                base_score += 30
            
            # 복잡도 보너스 (높은 복잡도일수록 우선)
            complexity = snippet["metadata"].get("complexity", 1.0)
            base_score += min(complexity * 2, 10)
            
            return base_score
        
        # 우선순위 기준으로 정렬
        all_snippets = sorted(state.code_snippets, key=get_priority_score, reverse=True)
        
        print(f"[DEBUG] 파일 우선순위 정렬 완료:")
        for i, snippet in enumerate(all_snippets[:5]):
            print(f"  {i+1}. {snippet['metadata'].get('file_path')} (우선순위: {get_priority_score(snippet)}, 실제내용: {snippet['metadata'].get('has_real_content')}, 중요도: {snippet['metadata'].get('importance')})")
        
        # 실제 내용이 있는 파일들만 필터링
        real_content_snippets = [s for s in all_snippets if s["metadata"].get("has_real_content", False)]
        
        print(f"[DEBUG] 실제 내용이 있는 파일: {len(real_content_snippets)}개")
        
        # 실제 내용이 있는 파일이 없으면 빈 리스트 반환
        if not real_content_snippets:
            print("[DEBUG] 실제 파일 내용이 없어서 코드 분석 질문 생성을 건너뜁니다.")
            return []
        
        for i in range(min(count, len(real_content_snippets))):
            snippet = real_content_snippets[i]
            
            print(f"[DEBUG] 질문 생성 중: {snippet['metadata'].get('file_path')} (실제내용: True)")
            
            try:
                # 실제 파일 내용이 있는 경우 - 추출된 요소들 활용
                extracted_elements = snippet["metadata"].get("extracted_elements", {})
                file_type = snippet["metadata"].get("file_type", "general")
                complexity = snippet["metadata"].get("complexity", 1.0)
                
                # 파일 유형별 맞춤 프롬프트 생성
                context_info = []
                if extracted_elements.get("classes"):
                    context_info.append(f"클래스: {', '.join(extracted_elements['classes'][:3])}")
                if extracted_elements.get("functions"):
                    context_info.append(f"주요 함수: {', '.join(extracted_elements['functions'][:3])}")
                if extracted_elements.get("imports"):
                    context_info.append(f"사용 라이브러리: {', '.join(extracted_elements['imports'][:2])}")
                
                context_str = " | ".join(context_info) if context_info else "기본 코드 구조"
                
                # 파일 경로 추출
                file_path = snippet["metadata"].get("file_path", "")
                
                # 파일 유형별 질문 스타일 조정
                if file_type == "controller":
                    question_focus = "HTTP 요청 처리, 라우팅, 에러 핸들링"
                elif file_type == "service":
                    question_focus = "비즈니스 로직, 데이터 처리, 트랜잭션"
                elif file_type == "model":
                    question_focus = "데이터 모델링, 관계 설정, 유효성 검사"
                elif file_type == "configuration":
                    question_focus = "설정 관리, 환경 분리, 보안"
                else:
                    question_focus = "코드 구조, 설계 패턴, 최적화"
                
                # 파일별 맞춤 프롬프트 생성 - 실제 파일 내용 기반
                if file_path.endswith("package.json"):
                    prompt = f"""
다음은 실제 프로젝트의 package.json 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== package.json 내용 ===
```json
{snippet["content"][:1500]}
```

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[핵심 질문을 1-2문장으로 명확하게]

**상황:**
[간단한 맥락이나 배경 1-2문장]

**요구사항:**
- [구체적 요구사항 1]
- [구체적 요구사항 2]
- [구체적 요구사항 3]

**평가 포인트:**
- [기술적 이해도 측정 요소]
- [실무 경험 확인 요소]

=== 내용 생성 요구사항 ===
- 실제 dependencies나 devDependencies 이름들을 직접 언급
- 실제 scripts 명령어들을 직접 참조  
- 실제 버전 정보나 설정값들을 구체적으로 언급
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 질문 하나만 생성해주세요.
"""
                elif file_path.endswith("pyproject.toml"):
                    prompt = f"""
다음은 실제 Python 프로젝트의 pyproject.toml 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== pyproject.toml 내용 ===
```toml
{snippet["content"][:1500]}
```

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[pyproject.toml 관련 핵심 질문 1-2문장]

**상황:**
[Python 프로젝트 맥락과 설정 배경]

**요구사항:**
- [구체적 설정 설명 요구사항]
- [도구 선택 이유 설명 요구사항]
- [프로젝트 특성 연관 설명 요구사항]

**평가 포인트:**
- [Python 빌드 시스템 이해도]
- [개발 도구 활용 경험]

=== 내용 생성 요구사항 ===
- 실제 build-system requirements를 직접 언급
- 실제 tool 설정들(isort, pytest 등)을 구체적으로 참조
- 실제 configuration 값들을 활용
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 질문 하나만 생성해주세요.
"""
                elif file_path.endswith("README.md") or file_path.endswith("README.rst"): 
                    prompt = f"""
다음은 실제 프로젝트의 README 파일입니다.

=== README 내용 ===
```
{snippet["content"][:1000]}
```

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[README 기반 프로젝트 이해 질문 1-2문장]

**상황:**
[프로젝트 특성과 README 역할 설명]

**요구사항:**
- [프로젝트 목적과 특징 설명 요구]
- [기술적 구현 방식 설명 요구]
- [실제 사용 경험 기반 설명 요구]

**평가 포인트:**
- [프로젝트 이해도]
- [기술적 판단 능력]

=== 내용 생성 요구사항 ===
- 실제 프로젝트 설명과 특징들을 직접 언급
- 실제 언급된 기능이나 구조를 구체적으로 참조
- 실제 설치나 기여 방법들을 활용
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 질문 하나만 생성해주세요:
"""
                else:
                    prompt = f"""
다음은 실제 프로젝트의 {file_type} 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== 파일 정보 ===
경로: {snippet["metadata"].get("file_path", "unknown")}
언어: {snippet["metadata"].get("language", "unknown")}
파일 유형: {file_type}
복잡도: {complexity:.1f}/10

=== 실제 코드 내용 ===
```{snippet["metadata"].get("language", "")}
{snippet["content"][:2000]}
```

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[코드 분석 관련 핵심 질문 1-2문장]

**상황:**
[파일의 역할과 프로젝트 내 위치 설명]

**요구사항:**
- [구체적 코드 구현 설명 요구]
- [설계 선택 이유 설명 요구]
- [최적화나 개선 방안 제시 요구]

**평가 포인트:**
- [{question_focus} 이해도]
- [실제 구현 경험]

=== 질문 생성 지침 ===
1. 위 코드에서 실제로 사용된 구체적인 함수명, 변수명, 클래스명을 질문에 포함하세요
2. 코드의 실제 로직과 구현 방식을 기반으로 질문하세요
3. {state.difficulty_level} 난이도에 맞는 기술적 깊이를 유지하세요
4. "만약", "가정", "일반적으로" 같은 추상적 표현 대신 코드의 실제 내용을 직접 언급하세요
5. 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 질문 하나만 생성해주세요:
"""
                
                # 프롬프트에 파일 내용이 포함되는지 상세 디버그 로그
                print(f"[QUESTION_GEN] ========== 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 대상 파일: {file_path}")
                print(f"[QUESTION_GEN] 파일 유형: {file_type}")
                print(f"[QUESTION_GEN] 파일 내용 길이: {len(snippet['content'])} 문자")
                print(f"[QUESTION_GEN] 실제 내용 여부: {snippet['metadata'].get('has_real_content', False)}")
                print(f"[QUESTION_GEN] 파일 내용 미리보기 (첫 200자):")
                print(f"[QUESTION_GEN] {snippet['content'][:200]}...")
                print(f"[QUESTION_GEN] ---------- AI에게 전송되는 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 질문 전체:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 질문 생성 완료 ==========")
                
                question = {
                    "id": f"code_analysis_{i}_{random.randint(1000, 9999)}",
                    "type": "code_analysis",
                    "question": ai_question,
                    "code_snippet": {
                        "content": snippet["content"][:800] + "..." if len(snippet["content"]) > 800 else snippet["content"],
                        "language": snippet["metadata"].get("language", "unknown"),
                        "file_path": snippet["metadata"].get("file_path", ""),
                        "complexity": snippet["metadata"].get("complexity", 1.0),
                        "has_real_content": True,
                        "file_type": snippet["metadata"].get("file_type", "general"),
                        "extracted_elements": snippet["metadata"].get("extracted_elements", {})
                    },
                    "difficulty": state.difficulty_level,
                    "time_estimate": self._estimate_question_time(snippet["metadata"].get("complexity", 1.0)),
                    "generated_by": "AI",
                    "source_file": snippet["metadata"].get("file_path", ""),
                    "importance": snippet["metadata"].get("importance", "medium"),
                    "file_type": snippet["metadata"].get("file_type", "general"),
                    "context": f"파일: {snippet['metadata'].get('file_path', 'unknown')} | 유형: {snippet['metadata'].get('file_type', 'general')} | 복잡도: {snippet['metadata'].get('complexity', 1.0):.1f}/10"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 질문 생성 실패 (파일: {snippet['metadata'].get('file_path')}): {e}")
                # AI 생성 실패 시 해당 파일은 건너뛰고 다음 파일로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_tech_stack_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """기술 스택 질문 생성"""
        
        questions = []
        
        # 분석 데이터에서 기술 스택 추출 (비중 5% 이상만)
        tech_stack = []
        print(f"[DEBUG] 분석 데이터 구조: {state.analysis_data.keys() if state.analysis_data else 'None'}")
        
        if state.analysis_data and "metadata" in state.analysis_data:
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            print(f"[DEBUG] tech_stack JSON 문자열: {tech_stack_str}")
            try:
                tech_stack_dict = json.loads(tech_stack_str)
                print(f"[DEBUG] 파싱된 기술 스택: {tech_stack_dict}")
                
                # 비중이 0.05 (5%) 이상인 기술만 선택
                tech_stack = [tech for tech, score in tech_stack_dict.items() if score >= 0.05]
                print(f"[DEBUG] 필터링된 기술 스택 (5% 이상): {tech_stack}")
            except Exception as e:
                print(f"[DEBUG] tech_stack JSON 파싱 실패: {e}")
                tech_stack = []
        else:
            print(f"[DEBUG] metadata 또는 tech_stack 필드가 분석 데이터에 없습니다.")
        
        if not tech_stack:
            # 기술 스택이 없는 경우 빈 리스트 반환
            print("[DEBUG] 유효한 기술 스택이 없어서 tech_stack 질문 생성을 건너뜁니다.")
            return []
        
        for i in range(count):
            tech = random.choice(tech_stack)
            
            # 실제 파일 내용을 기반으로 한 기술별 질문 생성
            try:
                # 분석된 파일 내용 가져오기
                file_context = ""
                if state.code_snippets:
                    file_info = []
                    for snippet in state.code_snippets[:3]:  # 최대 3개 파일
                        file_path = snippet["metadata"].get("file_path", "")
                        content_preview = snippet["content"][:300]
                        file_info.append(f"파일: {file_path}\n내용: {content_preview}...")
                    file_context = "\n\n".join(file_info)
                
                prompt = f"""
다음은 실제 프로젝트에서 {tech} 기술이 사용된 파일들입니다:

=== 실제 프로젝트 파일 내용 ===
{file_context}

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[{tech} 기술에 대한 핵심 질문 1-2문장]

**상황:**
[프로젝트 맥락과 {tech} 사용 배경]

**요구사항:**
- [실제 구현 관련 요구사항]
- [기술적 깊이 요구사항]
- [경험 기반 설명 요구사항]

**평가 포인트:**
- [{tech} 기술 이해도]
- [실제 프로젝트 경험]

=== 내용 요구사항 ===
- 실제 파일에서 사용된 구체적인 설정, 패키지, 코드를 직접 언급
- {state.difficulty_level} 난이도에 맞는 기술적 질문
- 일반적인 이론이 아닌 실제 구현 기반 질문
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 생성해주세요:
"""
                
                print(f"[QUESTION_GEN] ========== 기술스택 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 대상 기술: {tech}")
                print(f"[QUESTION_GEN] 파일 컨텍스트 길이: {len(file_context)} 문자")
                print(f"[QUESTION_GEN] 파일 컨텍스트 내용:")
                print(f"[QUESTION_GEN] {file_context[:500]}...")
                print(f"[QUESTION_GEN] ---------- 기술스택 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- 기술스택 AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 기술스택 질문:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 기술스택 질문 생성 완료 ==========")
                
                question = {
                    "id": f"tech_stack_{i}_{random.randint(1000, 9999)}",
                    "type": "tech_stack",
                    "question": ai_question,
                    "technology": tech,
                    "difficulty": state.difficulty_level,
                    "time_estimate": "3-5분",
                    "generated_by": "AI"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 기술 스택 질문 생성 실패 (기술: {tech}): {e}")
                # AI 생성 실패 시 해당 기술은 건너뛰고 다음으로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_architecture_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """아키텍처 질문 생성"""
        
        questions = []
        
        context = self._extract_architecture_context(state)
        
        # 실제 분석 데이터가 없으면 빈 리스트 반환
        if not context:
            return []
        
        for i in range(count):
            # AI를 활용한 프로젝트별 맞춤 아키텍처 질문 생성
            try:
                context_info = []
                if "project_type" in context:
                    context_info.append(f"프로젝트 타입: {context['project_type']}")
                if "scale" in context:
                    context_info.append(f"프로젝트 규모: {context['scale']}")
                if "deployment" in context:
                    context_info.append(f"배포 방식: {context['deployment']}")
                
                context_str = ", ".join(context_info) if context_info else "웹 애플리케이션"
                
                prompt = f"""
다음 프로젝트 정보를 바탕으로 아키텍처 관련 기술면접 질문을 생성해주세요.

프로젝트 정보: {context_str}

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[아키텍처 관련 핵심 질문]

**상황:**
[프로젝트 규모와 복잡성 설명]

**요구사항:**
- [아키텍처 설계 설명 요구]
- [확장성 고려사항 설명 요구]
- [기술 선택 이유 설명 요구]

**평가 포인트:**
- [아키텍처 설계 능력]
- [확장성 고려 능력]

=== 내용 요구사항 ===
- 프로젝트의 특성을 고려한 아키텍처 질문
- {state.difficulty_level} 난이도에 맞는 질문
- 실제 면접에서 나올 법한 실용적 질문
- 구체적이고 기술적인 질문
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성
- numbered list(1., 2., 3.) 사용 금지
- 마크다운 제목 형식(#, ##) 사용 금지

위 형식을 정확히 지켜서 하나의 완전한 질문만 생성해주세요:
"""
                
                print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 상세 로그 ==========")
                print(f"[QUESTION_GEN] 컨텍스트 정보: {context_str}")
                print(f"[QUESTION_GEN] ---------- 아키텍처 프롬프트 전체 내용 ----------")
                print(f"[QUESTION_GEN] 프롬프트 길이: {len(prompt)} 문자")
                print(f"[QUESTION_GEN] 프롬프트 내용:")
                print(prompt)
                print(f"[QUESTION_GEN] ---------- 프롬프트 전송 완료 ----------")
                
                # Gemini API 호출 (재시도 및 fallback 메커니즘 포함)
                try:
                    ai_response = await self._call_ai_with_retry(ai_service.generate_analysis, prompt, max_retries=3)
                    
                    # AI 응답 안전성 검증
                    if ai_response and isinstance(ai_response, dict) and "content" in ai_response and ai_response["content"]:
                        ai_question = ai_response["content"].strip()
                        if not ai_question:  # 빈 응답인 경우
                            raise Exception("AI 응답이 비어있음")
                    else:
                        raise Exception("AI 응답이 None이거나 형식이 올바르지 않음")
                        
                except Exception as ai_error:
                    print(f"[QUESTION_GEN] AI 질문 생성 실패, fallback 사용: {ai_error}")
                    # 기본적인 fallback 질문 생성
                    if "snippet" in locals() and snippet:
                        ai_question = f"이 {snippet['metadata'].get('file_type', '파일')}의 주요 기능과 구조를 분석하고 설명해주세요."
                    else:
                        ai_question = "프로젝트의 전반적인 구조와 설계 원칙을 분석해주세요."
                
                print(f"[QUESTION_GEN] ---------- 아키텍처 AI 응답 결과 ----------")
                print(f"[QUESTION_GEN] AI 응답 길이: {len(ai_question)} 문자")
                print(f"[QUESTION_GEN] 생성된 아키텍처 질문:")
                print(f"[QUESTION_GEN] {ai_question}")
                print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 완료 ==========")
                
                question = {
                    "id": f"architecture_{i}_{random.randint(1000, 9999)}",
                    "type": "architecture",
                    "question": ai_question,
                    "difficulty": state.difficulty_level,
                    "context": context_str,
                    "time_estimate": "10-15분",
                    "generated_by": "AI"
                }
                questions.append(question)
                
            except Exception as e:
                print(f"AI 아키텍처 질문 생성 실패: {e}")
                # AI 생성 실패 시 해당 질문은 건너뛰고 다음으로 진행
                # 더미/템플릿 질문은 생성하지 않음
                continue
        
        return questions
    
    async def _generate_single_code_analysis_question(self, snippet: Dict, state: QuestionState) -> Dict[str, Any]:
        """단일 코드 분석 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        extracted_elements = snippet["metadata"].get("extracted_elements", {})
        file_type = snippet["metadata"].get("file_type", "general")
        complexity = snippet["metadata"].get("complexity", 1.0)
        file_path = snippet["metadata"].get("file_path", "")
        
        # 기존 질문 생성 로직 사용
        context_info = []
        if extracted_elements.get("classes"):
            context_info.append(f"클래스: {', '.join(extracted_elements['classes'][:3])}")
        if extracted_elements.get("functions"):
            context_info.append(f"주요 함수: {', '.join(extracted_elements['functions'][:3])}")
        if extracted_elements.get("imports"):
            context_info.append(f"사용 라이브러리: {', '.join(extracted_elements['imports'][:2])}")
        
        context_str = " | ".join(context_info) if context_info else "기본 코드 구조"
        
        # 파일 유형별 질문 스타일 조정
        if file_type == "controller":
            question_focus = "HTTP 요청 처리, 라우팅, 에러 핸들링"
        elif file_type == "service":
            question_focus = "비즈니스 로직, 데이터 처리, 트랜잭션"
        elif file_type == "model":
            question_focus = "데이터 모델링, 관계 설정, 유효성 검사"
        elif file_type == "configuration":
            question_focus = "설정 관리, 환경 분리, 보안"
        else:
            question_focus = "코드 구조, 설계 패턴, 최적화"
        
        # 파일별 맞춤 프롬프트 생성
        if file_path.endswith("package.json"):
            prompt = f"""
다음은 실제 프로젝트의 package.json 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== package.json 내용 ===
```json
{snippet["content"][:1500]}
```

=== 질문 생성 요구사항 ===
위 package.json에서 실제로 보이는 내용을 바탕으로 질문하세요:
- 실제 dependencies나 devDependencies 이름들을 직접 언급
- 실제 scripts 명령어들을 직접 참조
- 실제 버전 정보나 설정값들을 구체적으로 언급
- "name", "version", "main" 필드의 실제 값들 활용

예시: "이 package.json에서 사용된 특정 의존성 패키지들의 선택 이유와 버전 관리 전략에 대해 설명해주세요."

실제 파일 내용을 직접 참조하는 구체적인 질문 하나만 생성하세요:
"""
        else:
            prompt = f"""
다음은 실제 프로젝트의 {file_type} 파일입니다. 이 파일의 구체적인 내용을 바탕으로 기술면접 질문을 생성해주세요.

=== 파일 정보 ===
경로: {file_path}
언어: {snippet["metadata"].get("language", "unknown")}
파일 유형: {file_type}
복잡도: {complexity:.1f}/10

=== 실제 코드 내용 ===
```{snippet["metadata"].get("language", "")}
{snippet["content"][:2000]}
```

=== 질문 생성 지침 ===
1. 위 코드에서 실제로 사용된 구체적인 함수명, 변수명, 클래스명을 질문에 포함하세요
2. 코드의 실제 로직과 구현 방식을 기반으로 질문하세요
3. {question_focus} 관점에서 심도 있는 질문을 만드세요
4. {state.difficulty_level} 난이도에 맞는 기술적 깊이를 유지하세요
5. "만약", "가정", "일반적으로" 같은 추상적 표현 대신 코드의 실제 내용을 직접 언급하세요

반드시 실제 코드 내용을 참조한 구체적인 질문 하나만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 코드 분석 질문 생성 상세 로그 ==========\n대상 파일: {file_path}\n파일 유형: {file_type}")
        
        # Gemini 기반 질문 생성
        try:
            ai_response = await ai_service.generate_analysis(
                prompt=prompt,
                provider=AIProvider.GEMINI_FLASH,
                api_keys=self.api_keys
            )
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] Gemini 코드분석 질문 생성 성공: {ai_question[:100]}...")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] Gemini 코드분석 질문 생성 실패: {e}, fallback 질문 사용")
            # Fallback 질문 생성
            ai_question = self._generate_fallback_code_question(snippet, state)
        
        return {
            "id": f"code_analysis_{random.randint(1000, 9999)}",
            "type": "code_analysis",
            "question": ai_question,
            "code_snippet": {
                "content": snippet["content"][:800] + "..." if len(snippet["content"]) > 800 else snippet["content"],
                "language": snippet["metadata"].get("language", "unknown"),
                "file_path": file_path,
                "complexity": complexity,
                "has_real_content": True,
                "file_type": file_type,
                "extracted_elements": extracted_elements
            },
            "difficulty": state.difficulty_level,
            "time_estimate": self._estimate_question_time(complexity),
            "generated_by": "AI",
            "source_file": file_path,
            "importance": snippet["metadata"].get("importance", "medium"),
            "file_type": file_type,
            "context": f"파일: {file_path} | 유형: {file_type} | 복잡도: {complexity:.1f}/10"
        }
        
    async def _generate_single_tech_stack_question(self, tech: str, file_context: str, state: QuestionState) -> Dict[str, Any]:
        """단일 기술 스택 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        prompt = f"""
다음은 실제 프로젝트에서 사용되고 있는 {tech} 기술입니다.

=== 프로젝트 파일 내용 ===
{file_context}

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[{tech} 기술에 대한 핵심 질문 1-2문장]

**상황:**
[프로젝트 맥락과 {tech} 사용 배경]

**요구사항:**
- [실제 구현 관련 요구사항]
- [기술적 깊이 요구사항]
- [경험 기반 설명 요구사항]

**평가 포인트:**
- [{tech} 기술 이해도]
- [실제 프로젝트 경험]

=== 내용 요구사항 ===
- 실제 파일에서 사용된 {tech} 관련 코드나 설정을 직접 참조
- {tech}의 특징과 장단점에 대한 심도 있는 질문
- 실제 프로젝트 경험을 바탕으로 한 질문
- {state.difficulty_level} 난이도에 맞는 기술적 깊이
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 질문 하나만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 기술 스택 질문 생성: {tech} ==========\n파일 컨텍스트 길이: {len(file_context)} 문자")
        
        try:
            ai_response = await ai_service.generate_analysis(prompt, api_keys=self.api_keys)
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] {tech} 기술스택 질문 생성 성공")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] Gemini 질문 생성 실패: {e}, fallback 질문 사용")
            # Fallback 질문 생성
            ai_question = f"이 프로젝트에서 {tech} 기술을 사용한 이유와 구현 방식에 대해 설명해주세요. 특히 다른 기술 대비 장점과 프로젝트에 적합한 이유를 중심으로 답변해주세요."
        
        return {
            "id": f"tech_stack_{random.randint(1000, 9999)}",
            "type": "tech_stack",
            "question": ai_question,
            "technology": tech,
            "difficulty": state.difficulty_level,
            "time_estimate": "7-10분",
            "generated_by": "AI",
            "context": f"{tech} 기술 스택 질문"
        }
        
    def _analyze_architecture_patterns(self, selected_files: List[Dict]) -> str:
        """선택된 파일들의 아키텍처 패턴 분석"""
        
        patterns = []
        technologies = set()
        file_types = set()
        
        for snippet in selected_files:
            # 기술 스택 수집
            language = snippet["metadata"].get("language", "")
            if language:
                technologies.add(language)
            
            # 파일 유형 수집
            file_type = snippet["metadata"].get("file_type", "")
            if file_type:
                file_types.add(file_type)
            
            # 파일 경로에서 패턴 추론
            file_path = snippet["metadata"].get("file_path", "")
            if "controller" in file_path.lower():
                patterns.append("MVC Controller 패턴")
            elif "service" in file_path.lower():
                patterns.append("Service Layer 패턴")
            elif "model" in file_path.lower():
                patterns.append("Domain Model 패턴")
            elif "component" in file_path.lower():
                patterns.append("Component 패턴")
        
        # 아키텍처 컨텍스트 생성
        context_parts = []
        if technologies:
            context_parts.append(f"사용 기술: {', '.join(sorted(technologies))}")
        if file_types:
            context_parts.append(f"파일 유형: {', '.join(sorted(file_types))}")
        if patterns:
            context_parts.append(f"감지된 패턴: {', '.join(patterns)}")
            
        return " | ".join(context_parts) if context_parts else "기본 프로젝트 구조"
        
    async def _generate_single_architecture_question(self, architecture_context: str, state: QuestionState) -> Dict[str, Any]:
        """단일 아키텍처 질문 생성"""
        
        from app.core.ai_service import ai_service
        
        prompt = f"""
다음은 실제 프로젝트의 아키텍처 분석 결과입니다.

=== 아키텍처 컨텍스트 ===
{architecture_context}

=== 질문 생성 형식 (반드시 준수) ===
다음 형식을 정확히 따라서 생성해주세요:

**질문:**
[아키텍처 관련 핵심 질문]

**상황:**
[프로젝트 규모와 복잡성 설명]

**요구사항:**
- [아키텍처 설계 설명 요구]
- [확장성 고려사항 설명 요구]
- [기술 선택 이유 설명 요구]

**평가 포인트:**
- [아키텍처 설계 능력]
- [확장성 고려 능력]

=== 내용 요구사항 ===
- 실제 프로젝트에서 사용된 아키텍처 패턴에 대한 질문
- 설계 결정의 이유와 트레이드오프에 대한 질문
- 확장성과 유지보수성 관점에서의 질문
- {state.difficulty_level} 난이도에 맞는 심도 있는 내용
- 각 섹션은 **볼드 제목:**으로 시작하고 그 아래 내용 작성

위 형식을 정확히 지켜서 하나의 완전한 질문만 생성해주세요:
"""
        
        print(f"[QUESTION_GEN] ========== 아키텍처 질문 생성 ==========\n컨텍스트: {architecture_context}")
        
        try:
            ai_response = await ai_service.generate_analysis(prompt, api_keys=self.api_keys)
            
            # AI 응답 null 체크 및 fallback 처리
            if ai_response and "content" in ai_response and ai_response["content"]:
                ai_question = ai_response["content"].strip()
                if ai_question:  # 빈 응답이 아닌 경우
                    print(f"[QUESTION_GEN] 아키텍처 질문 생성 성공")
                else:
                    raise ValueError("AI 응답이 비어있음")
            else:
                raise ValueError("AI 응답이 None이거나 content가 없음")
                
        except Exception as e:
            print(f"[QUESTION_GEN] Gemini 아키텍처 질문 생성 실패: {e}, fallback 질문 사용")
            # Fallback 질문 생성
            ai_question = "이 프로젝트의 전체적인 아키텍처 설계와 주요 구성 요소들의 역할에 대해 설명해주세요. 특히 확장성과 유지보수성을 고려한 설계 결정이 있다면 함께 설명해주세요."
        
        return {
            "id": f"architecture_{random.randint(1000, 9999)}",
            "type": "architecture",
            "question": ai_question,
            "difficulty": state.difficulty_level,
            "context": architecture_context,
            "time_estimate": "10-15분",
            "generated_by": "AI"
        }
    
    async def _generate_design_pattern_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """디자인 패턴 질문 생성"""
        
        questions = []
        
        # 분석 데이터에서 감지된 패턴 사용
        detected_patterns = []
        if state.analysis_data and "metadata" in state.analysis_data:
            # 기술 스택 기반으로 실제 패턴 추론
            tech_stack_str = state.analysis_data["metadata"].get("tech_stack", "{}")
            try:
                tech_stack_dict = json.loads(tech_stack_str)
                # 기술 스택에 따른 패턴 추론
                for tech in tech_stack_dict.keys():
                    tech_lower = tech.lower()
                    if tech_lower in ["react", "vue", "angular"]:
                        detected_patterns.extend(["Component", "Observer", "State Management"])
                    elif tech_lower in ["django", "spring", "express"]:
                        detected_patterns.extend(["MVC", "Factory", "Dependency Injection"])
                    elif tech_lower in ["java", "kotlin"]:
                        detected_patterns.extend(["Singleton", "Factory", "Builder"])
                    elif tech_lower in ["python", "flask"]:
                        detected_patterns.extend(["Decorator", "Factory", "Observer"])
                    elif tech_lower in ["javascript", "typescript"]:
                        detected_patterns.extend(["Module", "Prototype", "Factory"])
            except:
                pass
        
        # 패턴이 감지되지 않은 경우 빈 리스트 반환
        if not detected_patterns:
            return []
        
        for i in range(count):
            pattern = random.choice(detected_patterns)
            template = random.choice(templates)
            
            question = {
                "id": f"design_pattern_{i}_{random.randint(1000, 9999)}",
                "type": "design_patterns",
                "question": template.format(pattern=pattern),
                "pattern": pattern,
                "difficulty": state.difficulty_level,
                "time_estimate": "5-8분"
            }
            questions.append(question)
        
        return questions
    
    async def _generate_problem_solving_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """문제 해결 질문 생성"""
        
        questions = []
        
        for i in range(count):
            template = random.choice(templates)
            
            question = {
                "id": f"problem_solving_{i}_{random.randint(1000, 9999)}",
                "type": "problem_solving",
                "question": template,
                "difficulty": state.difficulty_level,
                "time_estimate": "10-20분"
            }
            questions.append(question)
        
        return questions
    
    async def _generate_best_practice_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """베스트 프랙티스 질문 생성"""
        
        questions = []
        
        for i in range(count):
            template = random.choice(templates)
            
            question = {
                "id": f"best_practices_{i}_{random.randint(1000, 9999)}",
                "type": "best_practices",
                "question": template,
                "difficulty": state.difficulty_level,
                "time_estimate": "5-10분"
            }
            questions.append(question)
        
        return questions
    
    def _generate_answer_points(self, template: str, snippet: Dict[str, Any]) -> List[str]:
        """예상 답변 포인트 생성"""
        
        points = []
        
        if "복잡도" in template:
            complexity = snippet["metadata"].get("complexity", 1.0)
            if complexity > 5:
                points.extend([
                    "시간 복잡도 분석",
                    "중첩 구조 개선 방안",
                    "알고리즘 최적화"
                ])
            else:
                points.extend([
                    "기본적인 복잡도 분석",
                    "코드 가독성 개선"
                ])
        
        elif "버그" in template or "문제점" in template:
            points.extend([
                "Null 체크 및 예외 처리",
                "메모리 누수 가능성",
                "동시성 문제",
                "입력 검증"
            ])
        
        elif "리팩토링" in template:
            points.extend([
                "함수 분리",
                "변수명 개선",
                "중복 코드 제거",
                "디자인 패턴 적용"
            ])
        
        elif "테스트" in template:
            points.extend([
                "경계값 테스트",
                "예외 상황 테스트",
                "Mock 객체 사용",
                "통합 테스트"
            ])
        
        return points
    
    def _infer_language_from_path(self, file_path: str) -> str:
        """파일 경로에서 언어 추론"""
        if not file_path:
            return "unknown"
        
        extension = file_path.split('.')[-1].lower() if '.' in file_path else ""
        
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'jsx': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'java': 'java',
            'kt': 'kotlin',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'rb': 'ruby',
            'cpp': 'cpp',
            'c': 'c',
            'cs': 'csharp',
            'swift': 'swift',
            'dart': 'dart',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'html': 'html',
            'css': 'css',
            'scss': 'scss',
            'sass': 'sass',
            'md': 'markdown',
            'sh': 'shell',
            'sql': 'sql'
        }
        
        return language_map.get(extension, extension or "unknown")
    
    def _determine_file_importance(self, file_path: str, file_content: str) -> str:
        """파일의 중요도를 자동으로 판단"""
        
        # 파일명 기반 중요도
        filename = file_path.lower()
        
        # 최고 우선순위 파일들
        if any(name in filename for name in ["main", "app", "index", "server", "config", "settings"]):
            return "very_high"
        
        # 높은 우선순위 파일들
        if any(name in filename for name in ["controller", "service", "model", "handler", "router", "api"]):
            return "high"
        
        # 중간 우선순위 파일들
        if any(name in filename for name in ["util", "helper", "component", "view", "template"]):
            return "medium"
        
        # 파일 내용 기반 중요도 (실제 내용이 있는 경우)
        if file_content and len(file_content) > 100:
            # 클래스나 함수가 많이 정의된 파일
            class_count = len(re.findall(r'\bclass\s+\w+', file_content, re.IGNORECASE))
            function_count = len(re.findall(r'\b(def|function|async\s+function)\s+\w+', file_content, re.IGNORECASE))
            
            if class_count >= 3 or function_count >= 5:
                return "high"
            elif class_count >= 1 or function_count >= 2:
                return "medium"
        
        return "low"
    
    def _categorize_file_type(self, file_path: str) -> str:
        """파일 유형 분류"""
        
        filename = file_path.lower()
        
        # 설정 파일
        if any(name in filename for name in ["config", "setting", "env", "docker", "package.json", "requirements"]):
            return "configuration"
        
        # 컨트롤러
        if "controller" in filename or "handler" in filename:
            return "controller"
        
        # 모델/엔티티
        if "model" in filename or "entity" in filename or "schema" in filename:
            return "model"
        
        # 서비스/비즈니스 로직
        if "service" in filename or "business" in filename:
            return "service"
        
        # 유틸리티
        if "util" in filename or "helper" in filename:
            return "utility"
        
        # 라우터/API
        if "router" in filename or "route" in filename or "api" in filename:
            return "router"
        
        # 컴포넌트 (프론트엔드)
        if "component" in filename or "view" in filename:
            return "component"
        
        # 메인 진입점
        if any(name in filename for name in ["main", "app", "index", "server"]):
            return "main"
        
        return "general"
    
    def _estimate_code_complexity(self, file_content: str) -> float:
        """코드 복잡도 추정"""
        
        if not file_content or len(file_content.strip()) < 10:
            return 1.0
        
        # 기본 복잡도 지표들
        lines = file_content.split('\n')
        line_count = len([line for line in lines if line.strip()])
        
        # 제어 구조 패턴 카운트
        control_patterns = [
            r'\bif\b', r'\belse\b', r'\belif\b', r'\bfor\b', r'\bwhile\b',
            r'\btry\b', r'\bcatch\b', r'\bswitch\b', r'\bcase\b'
        ]
        
        control_count = sum(len(re.findall(pattern, file_content, re.IGNORECASE)) for pattern in control_patterns)
        
        # 함수/클래스 정의 카운트
        function_count = len(re.findall(r'\b(def|function|async\s+function)\s+\w+', file_content, re.IGNORECASE))
        class_count = len(re.findall(r'\bclass\s+\w+', file_content, re.IGNORECASE))
        
        # 복잡도 계산 (1-10 스케일)
        complexity = 1.0
        complexity += min(line_count / 50, 3.0)  # 줄 수 기반 (최대 3점)
        complexity += min(control_count / 10, 2.0)  # 제어 구조 기반 (최대 2점)
        complexity += min(function_count / 5, 2.0)  # 함수 수 기반 (최대 2점)
        complexity += min(class_count / 2, 2.0)  # 클래스 수 기반 (최대 2점)
        
        return min(complexity, 10.0)
    
    def _extract_code_elements(self, file_content: str, language: str) -> Dict[str, List[str]]:
        """코드에서 주요 요소들 추출"""
        
        elements = {
            "classes": [],
            "functions": [],
            "imports": [],
            "variables": [],
            "constants": []
        }
        
        if not file_content or len(file_content.strip()) < 10:
            return elements
        
        # 언어별 패턴 매칭
        if language in ["python"]:
            # 클래스 추출
            classes = re.findall(r'class\s+(\w+)', file_content, re.IGNORECASE)
            elements["classes"] = classes[:10]  # 최대 10개
            
            # 함수 추출
            functions = re.findall(r'def\s+(\w+)', file_content, re.IGNORECASE)
            elements["functions"] = functions[:15]  # 최대 15개
            
            # import 추출
            imports = re.findall(r'(?:from\s+\w+\s+)?import\s+(\w+)', file_content, re.IGNORECASE)
            elements["imports"] = imports[:10]
            
        elif language in ["javascript", "typescript"]:
            # 클래스 추출
            classes = re.findall(r'class\s+(\w+)', file_content, re.IGNORECASE)
            elements["classes"] = classes[:10]
            
            # 함수 추출 (function 선언과 화살표 함수)
            functions = re.findall(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\()', file_content, re.IGNORECASE)
            elements["functions"] = [f[0] or f[1] for f in functions if f[0] or f[1]][:15]
            
            # import 추출
            imports = re.findall(r'import\s+(?:\{[^}]*\}|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]', file_content)
            elements["imports"] = imports[:10]
            
        elif language in ["java"]:
            # 클래스 추출
            classes = re.findall(r'(?:public\s+)?class\s+(\w+)', file_content, re.IGNORECASE)
            elements["classes"] = classes[:10]
            
            # 메서드 추출
            functions = re.findall(r'(?:public|private|protected)?\s*\w+\s+(\w+)\s*\(', file_content, re.IGNORECASE)
            elements["functions"] = functions[:15]
        
        return elements
    
    def _estimate_question_time(self, complexity: float) -> str:
        """복잡도에 따른 질문 답변 예상 시간 추정"""
        
        if complexity <= 2.0:
            return "3-5분"
        elif complexity <= 4.0:
            return "5-7분"
        elif complexity <= 6.0:
            return "7-10분"
        elif complexity <= 8.0:
            return "10-15분"
        else:
            return "15-20분"
    
    def _extract_context_summary(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """분석 컨텍스트 요약 추출"""
        
        if not analysis_data:
            return {}
        
        metadata = analysis_data.get("metadata", {})
        
        return {
            "tech_stack": json.loads(metadata.get("tech_stack", "{}")),
            "complexity_score": metadata.get("complexity_score", 0.0),
            "file_count": metadata.get("file_count", 0),
            "analysis_summary": analysis_data.get("analysis_text", "")[:200] + "..."
        }
    
    def _extract_architecture_context(self, state: QuestionState) -> Dict[str, Any]:
        """아키텍처 컨텍스트 추출"""
        
        context = {}
        
        if state.analysis_data:
            metadata = state.analysis_data.get("metadata", {})
            file_count = metadata.get("file_count", 0)
            
            # 프로젝트 규모 분석
            if file_count > 100:
                context["scale"] = "large"
            elif file_count > 20:
                context["scale"] = "medium"
            elif file_count > 0:
                context["scale"] = "small"
            
            # 기술 스택으로 프로젝트 타입 추론
            tech_stack_str = metadata.get("tech_stack", "{}")
            try:
                tech_stack = json.loads(tech_stack_str)
                tech_keys = [key.lower() for key in tech_stack.keys()]
                
                if any(tech in tech_keys for tech in ["react", "vue", "angular"]):
                    context["project_type"] = "SPA (Single Page Application)"
                elif any(tech in tech_keys for tech in ["django", "flask", "fastapi"]):
                    context["project_type"] = "REST API / Web Service"
                elif any(tech in tech_keys for tech in ["spring", "spring-boot"]):
                    context["project_type"] = "Enterprise Application"
                elif any(tech in tech_keys for tech in ["express", "koa", "nestjs"]):
                    context["project_type"] = "Node.js Web Application"
                elif "dockerfile" in tech_keys or "docker" in tech_keys:
                    context["deployment"] = "Docker 기반 배포"
            except:
                pass
        
        return context
    
    async def generate_follow_up_questions(self, original_question: Dict[str, Any], user_answer: str) -> List[Dict[str, Any]]:
        """후속 질문 생성"""
        
        follow_ups = []
        
        # AI 기반 후속 질문 생성 (임시 비활성화)
        # if self.llm and user_answer:
        #     try:
        #         # AI 생성 로직
        #         pass
        #     except Exception as e:
        #         print(f"AI 후속 질문 생성 오류: {e}")
        
        # 기본 후속 질문들
        if original_question["type"] == "code_analysis":
            follow_ups.append({
                "id": f"follow_up_{original_question['id']}_default_{random.randint(1000, 9999)}",
                "type": "follow_up",
                "question": "이와 비슷한 문제를 실무에서 어떻게 해결하셨나요?",
                "parent_question_id": original_question["id"],
                "time_estimate": "3-5분"
            })
        
        return follow_ups
    
    def _generate_fallback_code_question(self, snippet: Dict, state: QuestionState) -> str:
        """Gemini 실패 시 사용할 fallback 코드 질문 생성"""
        
        extracted_elements = snippet["metadata"].get("extracted_elements", {})
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        
        # 파일 유형별 기본 질문 템플맿
        if file_path.endswith("package.json"):
            return "이 package.json 파일에서 사용된 dependencies를 보고, 주요 라이브러리들의 역할과 선택 이유를 설명해주세요."
        elif file_path.endswith(".py"):
            if extracted_elements.get("functions"):
                func_name = extracted_elements["functions"][0]
                return f"이 Python 코드에서 `{func_name}` 함수의 주요 기능과 구현 방식을 설명해주세요."
            else:
                return "이 Python 코드의 전체적인 구조와 주요 기능을 설명해주세요."
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            if extracted_elements.get("functions"):
                func_name = extracted_elements["functions"][0]
                return f"이 JavaScript/TypeScript 코드에서 `{func_name}` 함수의 역할과 작동 원리를 설명해주세요."
            else:
                return "이 JavaScript/TypeScript 코드의 구조와 주요 기능을 설명해주세요."
        else:
            return f"이 {file_type} 코드의 주요 기능과 설계 의도를 설명해주세요."
    
    async def _generate_metadata_based_questions(self, state: QuestionState, snippets: List[Dict], count: int) -> List[Dict[str, Any]]:
        """파일 내용이 없을 때 메타데이터와 파일명 기반으로 질문 생성"""
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 시작 (요청: {count}개)")
        
        questions = []
        available_snippets = snippets[:count * 2]  # 더 많은 선택지 확보
        
        for i, snippet in enumerate(available_snippets):
            if len(questions) >= count:
                break
                
            file_path = snippet["metadata"].get("file_path", "unknown")
            file_type = snippet["metadata"].get("file_type", "general")
            importance = snippet["metadata"].get("importance", "medium")
            language = snippet["metadata"].get("language", "unknown")
            
            print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성: {file_path}")
            
            try:
                # 파일별 차별화된 프롬프트 생성
                question_text = self._generate_file_specific_question(snippet, state, i)
                
                if not question_text:
                    # 기본 프롬프트로 대체
                    question_text = self._generate_default_question_for_file_type(snippet)
                
                question = {
                    "id": f"metadata_based_{i}_{random.randint(1000, 9999)}",
                    "type": "code_analysis", 
                    "question": question_text,
                    "code_snippet": {
                        "content": f"# 파일: {file_path}\n# 타입: {file_type}\n# 언어: {language}\n# 중요도: {importance}\n\n# 내용을 직접 확인할 수 없지만, 파일명과 구조를 통해 분석할 수 있습니다.",
                        "language": language,
                        "file_path": file_path,
                        "complexity": 3.0,  # 메타데이터 기반이므로 중간 복잡도
                        "has_real_content": False,
                        "file_type": file_type,
                        "extracted_elements": {}
                    },
                    "difficulty": state.difficulty_level,
                    "time_estimate": "5-7분",  # 분석적 사고가 필요하므로 조금 더 길게
                    "generated_by": "metadata_template",
                    "source_file": file_path,
                    "importance": importance,
                    "file_type": file_type,
                    "context": f"파일: {file_path} | 유형: {file_type} | 언어: {language} | 메타데이터 기반 질문"
                }
                
                questions.append(question)
                print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 성공: {file_path}")
                
            except Exception as e:
                print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 실패 ({file_path}): {e}")
                continue
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 완료: {len(questions)}/{count}개")
        return questions
    
    def _generate_file_specific_question(self, snippet: Dict, state: QuestionState, question_index: int) -> str:
        """파일별로 차별화된 질문 생성"""
        
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        language = snippet["metadata"].get("language", "unknown")
        importance = snippet["metadata"].get("importance", "medium")
        
        # 파일 유형별 차별화된 질문 생성 (질문 인덱스 기반)
        if file_path.endswith("package.json"):
            if question_index == 0:
                return f"이 package.json의 dependencies 분석을 통해 프로젝트의 기술 스택 선택 이유와 각 라이브러리의 역할을 설명해주세요. 특히 버전 관리 전략도 포함해서 설명해주세요."
            elif question_index == 1:
                return f"package.json의 scripts 섹션을 분석하여 프로젝트의 빌드/배포 파이프라인과 개발 워크플로우를 설명해주세요."
            else:
                return f"package.json의 devDependencies와 dependencies 구분을 통해 프로덕션 vs 개발환경 분리 전략을 분석해주세요."
        
        elif file_path.endswith(("babel.config.js", "babel.config.json")):
            if question_index == 0:
                return f"이 Babel 설정 파일에서 사용된 플러그인들과 프리셋의 역할을 분석하고, 모던 JavaScript 개발에서 Babel이 해결하는 문제를 설명해주세요."
            elif question_index == 1:
                return f"Babel 설정에서 loose 모드와 useBuiltIns 옵션의 의미를 설명하고, 번들 크기와 성능에 미치는 영향을 분석해주세요."
            else:
                return f"이 Babel 설정이 지원하는 JavaScript 문법과 브라우저 호환성 전략을 분석해주세요."
        
        elif file_path.endswith(("webpack.config.js", "vite.config.js", "rollup.config.js")):
            if question_index == 0:
                return f"이 번들러 설정 파일({file_path})의 entry point와 output 설정을 분석하고, 모듈 번들링 전략을 설명해주세요."
            elif question_index == 1:
                return f"설정 파일에서 사용된 플러그인들의 역할과 최적화 설정이 빌드 성능에 미치는 영향을 분석해주세요."
            else:
                return f"개발환경과 프로덕션 환경에서 다르게 적용되는 번들링 최적화 설정을 분석해주세요."
        
        elif file_path.endswith(("requirements.txt", "pyproject.toml", "setup.py")):
            if question_index == 0:
                return f"이 Python 의존성 파일({file_path})에서 사용된 주요 라이브러리들의 용도와 버전 제약 조건의 이유를 분석해주세요."
            elif question_index == 1:
                return f"Python 패키지 관리에서 이 파일의 역할과 가상환경 관리 모범 사례를 설명해주세요."
            else:
                return f"의존성 충돌 해결과 보안 측면에서 이 파일의 중요성을 분석해주세요."
        
        elif file_path.endswith((".eslintrc", ".eslintrc.js", ".eslintrc.json")):
            if question_index == 0:
                return f"이 ESLint 설정에서 사용된 rules와 extends 설정을 분석하고, 코드 품질 향상에 미치는 영향을 설명해주세요."
            elif question_index == 1:
                return f"ESLint 설정에서 parser와 환경(env) 설정의 의미와 프로젝트별 커스터마이징 방법을 설명해주세요."
            else:
                return f"이 린트 설정이 팀 협업과 코드 일관성 유지에 어떻게 기여하는지 분석해주세요."
        
        elif file_path.endswith(("tsconfig.json", "jsconfig.json")):
            if question_index == 0:
                return f"이 TypeScript/JavaScript 컴파일러 설정에서 compilerOptions의 주요 옵션들과 타입 안정성에 미치는 영향을 분석해주세요."
            elif question_index == 1:
                return f"경로 매핑(paths)과 모듈 해상도 설정이 대규모 프로젝트 구조에 미치는 영향을 설명해주세요."
            else:
                return f"strict 모드와 관련 옵션들이 코드 품질과 개발 생산성에 미치는 영향을 분석해주세요."
        
        elif file_path.endswith((".gitignore", ".dockerignore")):
            if question_index == 0:
                return f"이 ignore 파일({file_path})의 패턴 분석을 통해 프로젝트의 구조와 보안 고려사항을 설명해주세요."
            elif question_index == 1:
                return f"버전 관리에서 제외되는 파일들의 선택 기준과 협업 시 주의사항을 분석해주세요."
            else:
                return f"이 ignore 설정이 빌드 성능과 배포 최적화에 미치는 영향을 설명해주세요."
        
        elif file_path.endswith(("README.md", "CONTRIBUTING.md", "CHANGELOG.md")):
            if question_index == 0:
                return f"이 문서 파일({file_path})에서 다루어야 할 핵심 내용과 오픈소스 프로젝트 관리에서의 중요성을 설명해주세요."
            elif question_index == 1:
                return f"좋은 기술 문서 작성의 원칙과 개발자 커뮤니티 참여를 촉진하는 방법을 분석해주세요."
            else:
                return f"문서화가 프로젝트 유지보수성과 신규 개발자 온보딩에 미치는 영향을 설명해주세요."
        
        elif 'test' in file_path.lower() or 'spec' in file_path.lower():
            if question_index == 0:
                return f"이 테스트 파일({file_path})에서 사용될 것으로 예상되는 테스트 패턴과 전략을 분석하고, 테스트 주도 개발(TDD)의 장점을 설명해주세요."
            elif question_index == 1:
                return f"단위 테스트, 통합 테스트, E2E 테스트의 차이점과 이 파일이 담당하는 테스트 범위를 분석해주세요."
            else:
                return f"테스트 커버리지와 코드 품질의 관계, 그리고 효과적인 테스트 작성 방법을 설명해주세요."
        
        elif language == "python":
            if question_index == 0:
                return f"이 Python 파일({file_path})에서 예상되는 주요 디자인 패턴과 Python다운 코드 작성 원칙(Pythonic)을 설명해주세요."
            elif question_index == 1:
                return f"Python의 모듈/패키지 시스템과 이 파일이 프로젝트 전체 아키텍처에서 담당하는 역할을 분석해주세요."
            else:
                return f"Python 성능 최적화 기법과 메모리 관리, 그리고 이 파일에서 적용 가능한 개선사항을 분석해주세요."
        
        elif language in ["javascript", "typescript"]:
            if question_index == 0:
                return f"이 {language} 파일({file_path})에서 사용될 것으로 예상되는 ES6+ 문법과 함수형/객체지향 프로그래밍 패러다임을 설명해주세요."
            elif question_index == 1:
                return f"JavaScript/TypeScript의 비동기 처리 패턴과 이 파일에서의 활용 방안을 분석해주세요."
            else:
                return f"모듈 시스템(CommonJS vs ES6 modules)과 번들링 최적화가 이 파일에 미치는 영향을 설명해주세요."
        
        else:
            # 기타 파일들에 대한 기본 질문
            return None  # 기본 프롬프트 사용
    
    def _generate_default_question_for_file_type(self, snippet: Dict) -> str:
        """파일 타입별 기본 질문 생성"""
        
        file_path = snippet["metadata"].get("file_path", "")
        file_type = snippet["metadata"].get("file_type", "general")
        language = snippet["metadata"].get("language", "unknown")
        
        if file_path.endswith(("Dockerfile", "docker-compose.yml", "docker-compose.yaml")):
            return f"이 컨테이너화 설정 파일({file_path})을 통해 애플리케이션 배포 전략을 분석하고, Docker 사용의 장점과 고려사항을 설명해주세요."
        
        elif file_path.endswith((".yml", ".yaml")) and any(keyword in file_path.lower() for keyword in ["ci", "cd", "github", "action", "workflow"]):
            return f"이 CI/CD 설정 파일({file_path})의 역할과 지속적 통합/배포 파이프라인에서의 중요성을 설명해주세요."
        
        elif file_path.endswith((".env", ".env.example")):
            return f"환경변수 설정 파일({file_path})의 역할과 보안을 고려한 환경변수 관리 방법을 설명해주세요."
        
        else:
            return f"프로젝트에서 {file_path} 파일의 역할과 중요성을 분석하고, 이런 유형의 파일이 소프트웨어 개발 프로세스에서 어떤 가치를 제공하는지 설명해주세요."
        
        print(f"[QUESTION_GEN] 메타데이터 기반 질문 생성 완료: {len(questions)}/{count}개")
        return questions
    
    async def _generate_template_questions(self, state: QuestionState, question_types: List[str], count: int) -> List[Dict[str, Any]]:
        """실패한 질문 타입들을 위한 템플릿 기반 질문 생성"""
        
        print(f"[QUESTION_GEN] 템플릿 기반 질문 생성 시작 (타입: {question_types}, 개수: {count})")
        
        questions = []
        questions_per_type = max(1, count // len(question_types))
        
        for question_type in question_types:
            type_count = min(questions_per_type, count - len(questions))
            if type_count <= 0:
                break
                
            try:
                if question_type == "code_analysis":
                    template_questions = self._get_code_analysis_templates(state, type_count)
                elif question_type == "tech_stack":
                    template_questions = self._get_tech_stack_templates(state, type_count)
                elif question_type == "architecture":
                    template_questions = self._get_architecture_templates(state, type_count)
                else:
                    template_questions = self._get_general_templates(state, question_type, type_count)
                
                questions.extend(template_questions)
                print(f"[QUESTION_GEN] {question_type} 템플릿 질문 {len(template_questions)}개 생성")
                
            except Exception as e:
                print(f"[QUESTION_GEN] {question_type} 템플릿 질문 생성 실패: {e}")
        
        return questions[:count]
    
    async def _generate_general_template_questions(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """일반적인 템플릿 기반 질문 생성"""
        
        print(f"[QUESTION_GEN] 일반 템플릿 질문 생성: {count}개")
        
        questions = []
        general_templates = [
            ("tech_stack", "이 프로젝트에서 사용된 주요 기술 스택의 장단점과 선택 이유를 설명해주세요."),
            ("architecture", "이 프로젝트의 전체적인 아키텍처 구조와 주요 컴포넌트들의 역할을 설명해주세요."),
            ("code_analysis", "프로젝트의 코드 품질과 유지보수성을 높이기 위한 개선 방안을 제시해주세요."),
            ("best_practices", "이 프로젝트에서 적용된 개발 베스트 프랙티스와 그 효과를 설명해주세요."),
            ("problem_solving", "프로젝트 개발 과정에서 발생할 수 있는 주요 문제점들과 해결 방안을 설명해주세요.")
        ]
        
        for i in range(count):
            template_type, template_text = general_templates[i % len(general_templates)]
            
            question = {
                "id": f"general_template_{i}_{random.randint(1000, 9999)}",
                "type": template_type,
                "question": template_text,
                "difficulty": state.difficulty_level,
                "time_estimate": "5분",
                "generated_by": "general_template",
                "context": "일반 템플릿 기반 질문"
            }
            
            questions.append(question)
        
        return questions
    
    def _get_code_analysis_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """코드 분석 템플릿 질문들"""
        
        templates = [
            "프로젝트의 코드 구조와 모듈화 방식을 분석하고, 개선할 수 있는 부분을 제시해주세요.",
            "코드의 가독성과 유지보수성을 높이기 위해 적용할 수 있는 리팩토링 기법들을 설명해주세요.",
            "프로젝트에서 사용된 디자인 패턴들을 식별하고, 그 효과와 적용 이유를 설명해주세요.",
            "코드 품질 측정 지표들을 활용하여 이 프로젝트의 코드 품질을 평가해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"code_template_{i}_{random.randint(1000, 9999)}",
                "type": "code_analysis",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "7분",
                "generated_by": "code_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_tech_stack_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """기술 스택 템플릿 질문들"""
        
        templates = [
            "프로젝트에서 사용된 주요 프레임워크와 라이브러리들의 선택 기준과 장점을 설명해주세요.",
            "현재 기술 스택의 확장성과 성능 측면에서의 장단점을 분석해주세요.",
            "프로젝트의 기술 스택을 다른 대안들과 비교하여 평가해주세요.",
            "최신 기술 트렌드를 고려하여 현재 기술 스택의 미래 지향성을 평가해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"tech_template_{i}_{random.randint(1000, 9999)}",
                "type": "tech_stack",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "6분",
                "generated_by": "tech_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_architecture_templates(self, state: QuestionState, count: int) -> List[Dict[str, Any]]:
        """아키텍처 템플릿 질문들"""
        
        templates = [
            "프로젝트의 전체 아키텍처 구조를 설명하고, 각 계층의 역할과 책임을 설명해주세요.",
            "시스템의 확장성과 가용성을 고려한 아키텍처 설계 원칙들을 설명해주세요.",
            "마이크로서비스 vs 모노리스 관점에서 현재 아키텍처의 장단점을 분석해주세요.",
            "보안과 성능을 고려한 아키텍처 최적화 방안을 제시해주세요."
        ]
        
        questions = []
        for i in range(min(count, len(templates))):
            question = {
                "id": f"arch_template_{i}_{random.randint(1000, 9999)}",
                "type": "architecture",
                "question": templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "8분",
                "generated_by": "architecture_template"
            }
            questions.append(question)
        
        return questions
    
    def _get_general_templates(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """기타 질문 타입들의 템플릿"""
        
        templates = {
            "design_patterns": [
                "프로젝트에서 적용할 수 있는 디자인 패턴들과 그 활용 방안을 설명해주세요."
            ],
            "problem_solving": [
                "프로젝트 개발 과정에서 발생할 수 있는 기술적 문제들과 해결 전략을 설명해주세요."
            ],
            "best_practices": [
                "코딩 표준과 개발 베스트 프랙티스가 프로젝트에 미치는 영향을 설명해주세요."
            ]
        }
        
        question_templates = templates.get(question_type, ["프로젝트의 특성을 분석하고 개선 방안을 제시해주세요."])
        
        questions = []
        for i in range(min(count, len(question_templates))):
            question = {
                "id": f"{question_type}_template_{i}_{random.randint(1000, 9999)}",
                "type": question_type,
                "question": question_templates[i],
                "difficulty": state.difficulty_level,
                "time_estimate": "6분",
                "generated_by": f"{question_type}_template"
            }
            questions.append(question)
        
        return questions    
    async def _call_ai_with_retry(self, ai_function, prompt: str, max_retries: int = 3, provider: "AIProvider" = None) -> Dict[str, Any]:
        """AI 서비스 호출에 재시도 메커니즘 추가"""
        
        import asyncio
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                print(f"[QUESTION_GEN] AI 호출 시도 {attempt + 1}/{max_retries}")
                
                # provider가 지정되어 있으면 해당 provider로 호출
                if provider:
                    result = await ai_function(prompt=prompt, provider=provider, api_keys=self.api_keys)
                else:
                    result = await ai_function(prompt, api_keys=self.api_keys)
                
                # 응답 검증
                if result and "content" in result and result["content"].strip():
                    print(f"[QUESTION_GEN] AI 호출 성공 (시도 {attempt + 1})")
                    return result
                else:
                    print(f"[QUESTION_GEN] AI 응답이 비어있음 (시도 {attempt + 1})")
                    last_exception = Exception("Empty AI response")
                    
            except Exception as e:
                last_exception = e
                print(f"[QUESTION_GEN] AI 호출 실패 (시도 {attempt + 1}): {str(e)}")
                
                # 마지막 시도가 아닌 경우 잠시 대기
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2초, 4초, 6초...
                    print(f"[QUESTION_GEN] {wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
        
        # 모든 재시도가 실패한 경우
        print(f"[QUESTION_GEN] AI 호출 최종 실패 - 모든 재시도 완료")
        if last_exception:
            raise last_exception
        else:
            raise Exception("All AI call attempts failed")
    
    async def _generate_fallback_questions(self, state: QuestionState, question_type: str, count: int, question_index: int) -> List[Dict[str, Any]]:
        """AI 생성 실패 시 사용할 fallback 질문 생성"""
        
        print(f"[QUESTION_GEN] fallback 질문 생성 시작: {question_type} 타입, {count}개")
        
        fallback_questions = []
        
        # 기본 메타데이터 추출
        repo_name = "프로젝트"
        tech_stack = []
        
        if state.analysis_data and "metadata" in state.analysis_data:
            metadata = state.analysis_data["metadata"]
            repo_name = metadata.get("repo_name", "프로젝트")
            
            # 기술 스택 추출
            try:
                tech_stack_str = metadata.get("tech_stack", "{}")
                tech_stack_dict = json.loads(tech_stack_str) if isinstance(tech_stack_str, str) else tech_stack_str
                if isinstance(tech_stack_dict, dict):
                    for category, techs in tech_stack_dict.items():
                        if isinstance(techs, list):
                            tech_stack.extend(techs)
                        elif isinstance(techs, str):
                            tech_stack.append(techs)
            except:
                tech_stack = ["Python", "JavaScript", "React", "FastAPI"]
        
        # 선택된 파일 정보 가져오기
        selected_file_info = None
        if state.code_snippets:
            try:
                selected_files = self._get_files_for_question_index(state.code_snippets, question_index)
                if selected_files:
                    selected_file_info = selected_files[0]
            except:
                selected_file_info = state.code_snippets[0] if state.code_snippets else None
        
        # 타입별 fallback 질문 생성
        for i in range(count):
            question_id = f"fallback_{question_type}_{question_index}_{i}"
            
            if question_type == "code_analysis":
                if selected_file_info:
                    file_path = selected_file_info["metadata"].get("file_path", "unknown")
                    question_text = f"{file_path} 파일의 주요 기능과 구조에 대해 설명해주세요."
                else:
                    question_text = f"{repo_name}의 핵심 코드 구조와 주요 컴포넌트에 대해 설명해주세요."
                    
            elif question_type == "tech_stack":
                if tech_stack:
                    tech = tech_stack[i % len(tech_stack)]
                    question_text = f"이 프로젝트에서 {tech}를 선택한 이유와 어떻게 활용했는지 설명해주세요."
                else:
                    question_text = f"{repo_name}에서 사용한 주요 기술 스택과 그 선택 이유를 설명해주세요."
                    
            elif question_type == "architecture":
                question_text = f"{repo_name}의 전체 아키텍처 설계 패턴과 주요 설계 결정사항에 대해 설명해주세요."
                
            else:
                question_text = f"{repo_name}의 {question_type} 관련하여 중요한 구현 결정사항과 그 이유를 설명해주세요."
            
            fallback_question = {
                "id": question_id,
                "type": question_type,
                "question": question_text,
                "difficulty": state.difficulty_level,
                "context": f"{repo_name} 프로젝트 분석",
                "time_estimate": "5분",
                "technology": tech_stack[0] if tech_stack else "General",
                "pattern": "fallback",
                "metadata": {
                    "is_fallback": True,
                    "generation_method": "template",
                    "question_index": question_index
                }
            }
            
            fallback_questions.append(fallback_question)
            print(f"[QUESTION_GEN] fallback 질문 생성: {question_text[:50]}...")
        
        print(f"[QUESTION_GEN] fallback 질문 {len(fallback_questions)}개 생성 완료")
        return fallback_questions
    
    async def _generate_template_questions(self, state: QuestionState, question_type: str, count: int) -> List[Dict[str, Any]]:
        """템플릿 기반 질문 생성 (최후 보장 메커니즘)"""
        
        print(f"[QUESTION_GEN] 템플릿 질문 생성 시작: {question_type} 타입, {count}개")
        
        template_questions = []
        
        # 기본 템플릿 질문들
        question_templates = {
            "code_analysis": [
                "이 프로젝트의 핵심 알고리즘이나 비즈니스 로직에 대해 설명해주세요.",
                "코드의 복잡한 부분이나 도전적인 구현 사항에 대해 설명해주세요.",
                "성능 최적화를 위해 어떤 방법을 사용했는지 설명해주세요.",
                "코드 리뷰 시 주의 깊게 봐야 할 부분과 그 이유를 설명해주세요.",
                "이 프로젝트에서 가장 중요한 모듈이나 컴포넌트에 대해 설명해주세요."
            ],
            "tech_stack": [
                "이 프로젝트에서 사용한 주요 기술들의 장단점을 설명해주세요.",
                "기술 스택 선택 시 고려했던 요소들과 그 이유를 설명해주세요.",
                "다른 대안 기술들과 비교했을 때 현재 선택의 이유를 설명해주세요.",
                "프로젝트 진행 중 기술 스택 관련해서 어려움이 있었다면 어떻게 해결했는지 설명해주세요.",
                "향후 기술 스택 업그레이드나 변경 계획이 있다면 설명해주세요."
            ],
            "architecture": [
                "이 프로젝트의 전체 아키텍처 패턴과 그 선택 이유를 설명해주세요.",
                "확장성을 고려한 설계 부분에 대해 설명해주세요.",
                "모듈 간의 의존성 관리는 어떻게 하고 있는지 설명해주세요.",
                "데이터 흐름과 상태 관리 방식에 대해 설명해주세요.",
                "시스템의 병목점이나 성능 이슈가 예상되는 부분과 대응책을 설명해주세요."
            ]
        }
        
        # 기본 템플릿이 없는 경우 일반적인 질문 사용
        templates = question_templates.get(question_type, [
            f"이 프로젝트의 {question_type} 관련 주요 특징에 대해 설명해주세요.",
            f"{question_type}와 관련된 구현상의 도전과제와 해결방안을 설명해주세요.",
            f"프로젝트에서 {question_type} 측면에서 가장 중요한 부분은 무엇인지 설명해주세요."
        ])
        
        for i in range(count):
            template_index = i % len(templates)
            question_id = f"template_{question_type}_{i}"
            
            template_question = {
                "id": question_id,
                "type": question_type,
                "question": templates[template_index],
                "difficulty": state.difficulty_level,
                "context": "프로젝트 일반 분석",
                "time_estimate": "5분",
                "technology": "General",
                "pattern": "template",
                "metadata": {
                    "is_template": True,
                    "generation_method": "template",
                    "template_index": template_index
                }
            }
            
            template_questions.append(template_question)
            print(f"[QUESTION_GEN] 템플릿 질문 생성: {templates[template_index][:50]}...")
        
        print(f"[QUESTION_GEN] 템플릿 질문 {len(template_questions)}개 생성 완료")
        return template_questions
