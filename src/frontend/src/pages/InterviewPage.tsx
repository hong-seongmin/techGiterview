import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  MessageCircle,
  Clock,
  Sun,
  Moon,
  Settings,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Send,
  Save,
  Trash2,
  HelpCircle,
  CheckCircle,
  Code,
  Database,
  Server,
  Layers,
  Shield,
  Bug,
  Zap,
  Terminal,
  Monitor,
  Palette,
  FileText,
  Lightbulb
} from 'lucide-react'
import { AppShellV2 } from '../components/v2/AppShellV2'
import { AnswerFeedback } from '../components/AnswerFeedback'
import { debugLog } from '../utils/debugUtils'
import { buildQuestionPreviewText, formatQuestionForDisplay } from '../utils/questionFormatter'
import { useResizableSidebar } from '../hooks/useResizableSidebar'
import './InterviewPage.css'

interface Question {
  id: string
  question: string
  question_headline?: string
  question_details_markdown?: string
  question_has_details?: boolean
  category: string
  difficulty: string
  context?: string
  parent_question_id?: string
  sub_question_index?: number
  total_sub_questions?: number
  is_compound_question?: boolean
}

interface InterviewData {
  interview_id: string
  analysis_id: string
  repo_url: string
  status: 'active' | 'paused' | 'completed'
  interview_type: string
  difficulty_level: string
  started_at: string
  progress: {
    current_question: number
    total_questions: number
    progress_percentage: number
    elapsed_time: number
    remaining_time: number
  }
}

interface Message {
  id: string
  type: 'system' | 'question' | 'answer' | 'feedback'
  content: string
  timestamp: Date
  question_id?: string
  feedback?: AnswerFeedbackData
}

interface AnswerFeedbackData {
  overall_score?: number
  criteria_scores?: {
    technical_accuracy: number
    problem_solving: number
    communication: number
  }
  feedback?: string
  suggestions: string[]
  is_conversation?: boolean
  // 기존 필드들 (호환성 유지)
  score?: number
  message?: string
  feedback_type?: 'strength' | 'improvement' | 'suggestion' | 'keyword_missing'
  details?: string
  keywords_found?: string[]
  keywords_missing?: string[]
  technical_accuracy?: string
}

export const InterviewPage: React.FC = () => {
  const { analysisId, interviewId } = useParams<{ analysisId?: string; interviewId: string }>()
  const navigate = useNavigate()
  
  const [interview, setInterview] = useState<InterviewData | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [currentAnswer, setCurrentAnswer] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [loadingStates, setLoadingStates] = useState({
    session: true,
    questions: true
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [timeRemaining, setTimeRemaining] = useState(30 * 60) // 30분
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [fontSize, setFontSize] = useState('medium')
  const [currentFeedback] = useState<AnswerFeedbackData | null>(null)
  const [showFeedback] = useState(false)
  const [isFocusMode, setIsFocusMode] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const [isAnswerInputFocused, setIsAnswerInputFocused] = useState(false)
  const [isTipsCollapsed, setIsTipsCollapsed] = useState(true)
  const [isHeaderSettingsOpen, setIsHeaderSettingsOpen] = useState(false)
  const [isFinishConfirmOpen, setIsFinishConfirmOpen] = useState(false)
  const [isFinishingInterview, setIsFinishingInterview] = useState(false)
  const [conversationMode, setConversationMode] = useState<{
    questionId: string;
    originalAnswer: string;
    feedback: AnswerFeedbackData;
  } | null>(null)
  const {
    width: sidebarWidth,
    isResizing: isResizingSidebar,
    startResize: startSidebarResize,
    resetWidth: resetSidebarWidth
  } = useResizableSidebar({
    storageKey: 'techgiterview_interview_sidebar_width',
    defaultWidth: 300,
    minWidth: 240,
    maxWidth: 420
  })
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const autoSaveTimer = useRef<NodeJS.Timeout | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const questionContainerRef = useRef<HTMLDivElement>(null)
  const inputHeaderRef = useRef<HTMLDivElement>(null)
  const headerSettingsRef = useRef<HTMLDivElement>(null)

  // WebSocket 연결
  useEffect(() => {
    if (!interviewId) return

    // 임시로 WebSocket 없이 진행
    setWsConnected(true)
    
    // const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/interview/${interviewId}`
    // const ws = new WebSocket(wsUrl)
    
    // ws.onopen = () => {
    //   console.log('WebSocket connected')
    //   setWsConnected(true)
    // }
    
    // ws.onmessage = (event) => {
    //   const data = JSON.parse(event.data)
    //   handleWebSocketMessage(data)
    // }
    
    // ws.onclose = () => {
    //   console.log('WebSocket disconnected')
    //   setWsConnected(false)
    // }
    
    // ws.onerror = (error) => {
    //   console.error('WebSocket error:', error)
    //   setWsConnected(false)
    // }
    
    // wsRef.current = ws

    return () => {
      // if (ws && ws.readyState === WebSocket.OPEN) {
      //   ws.close()
      // }
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [interviewId])

  // 면접 데이터 로드
  useEffect(() => {
    if (!interviewId) {
      navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard')
      return
    }
    
    loadInterview()
  }, [interviewId, navigate])

  // 타이머 시작
  useEffect(() => {
    if (interview && interview.status === 'active') {
      timerRef.current = setInterval(() => {
        setTimeRemaining(prev => {
          if (prev <= 1) {
            // 타이머 콜백에서 무거운 작업 방지 - 다음 틱에서 실행
            setTimeout(() => finishInterview(), 0)
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [interview])

  // 메시지 스크롤
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 키보드 단축키 처리
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'Enter':
            e.preventDefault()
            submitAnswer()
            break
          case 'ArrowLeft':
            e.preventDefault()
            navigateQuestion(-1)
            break
          case 'ArrowRight':
            e.preventDefault()
            navigateQuestion(1)
            break
          case 'd':
            e.preventDefault()
            setIsDarkMode(!isDarkMode)
            break
          case 's':
            e.preventDefault()
            saveCurrentAnswer()
            break
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isDarkMode, currentQuestionIndex])

  useEffect(() => {
    if (!isFinishConfirmOpen) return

    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isFinishingInterview) {
        setIsFinishConfirmOpen(false)
      }
    }

    window.addEventListener('keydown', handleEscapeKey)
    return () => window.removeEventListener('keydown', handleEscapeKey)
  }, [isFinishConfirmOpen, isFinishingInterview])

  useEffect(() => {
    if (!isHeaderSettingsOpen) return

    const handleOutsideClick = (event: MouseEvent) => {
      if (!headerSettingsRef.current) return
      if (event.target instanceof Node && !headerSettingsRef.current.contains(event.target)) {
        setIsHeaderSettingsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [isHeaderSettingsOpen])

  // 자동 저장 기능
  useEffect(() => {
    const currentQ = questions[currentQuestionIndex]
    if (currentAnswer && interviewId && currentQ) {
      if (autoSaveTimer.current) {
        clearTimeout(autoSaveTimer.current)
      }
      
      autoSaveTimer.current = setTimeout(() => {
        saveCurrentAnswer()
      }, 2000) // 2초 후 자동 저장
    }

    return () => {
      if (autoSaveTimer.current) {
        clearTimeout(autoSaveTimer.current)
      }
    }
  }, [currentAnswer, interviewId, questions, currentQuestionIndex])

  // 질문 변경 시 답변 로드 및 textarea 상단 스크롤
  useEffect(() => {
    const currentQ = questions[currentQuestionIndex]
    if (currentQ && interviewId) {
      const savedKey = `interview_${interviewId}_${currentQ.id}`
      const saved = localStorage.getItem(savedKey)
      setCurrentAnswer(saved || '')

      // 답변 로드 후 textarea 상단으로 스크롤
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.scrollTop = 0
        }
      }, 100)
    }
  }, [currentQuestionIndex, interviewId, questions])

  // 답변 초기화 시 textarea 상단 스크롤
  useEffect(() => {
    if (currentAnswer === '' && textareaRef.current) {
      textareaRef.current.scrollTop = 0
    }
  }, [currentAnswer])

  // 세션 히스토리 로딩 (답변, 피드백, 대화 포함)
  const loadSessionHistory = async (questionsList: Question[], _sessionData: any) => {
    if (!interviewId) return

    try {
      debugLog.info('history', '세션 히스토리 로딩 시작');
      const response = await fetch(`/api/v1/interview/session/${interviewId}/data`)
      
      if (!response.ok) {
        console.warn('[세션 데이터] 불러오기 실패:', response.status)
        // 데이터 로딩 실패 시에도 기본 진행률 표시
        setMessages(prev => [...prev, {
          id: 'history-load-failed',
          type: 'system',
          content: '이전 답변 기록을 불러올 수 없었습니다. 새로 시작합니다.',
          timestamp: new Date()
        }])
        return
      }
      
      const { data } = await response.json()
      debugLog.info('history', '세션 데이터 로드 완료', { sessionData: data })
      
      // 답변 히스토리를 메시지로 변환
      const historyMessages: Message[] = []
      
      // 질문별 답변 맵핑 생성
      const answersByQuestion = new Map()
      data.answers.forEach((answer: any) => {
        answersByQuestion.set(answer.question_id, answer)
      })
      
      // 질문 순서대로 답변과 피드백 추가
      questionsList.forEach((question) => {
        const answer = answersByQuestion.get(question.id)
        if (answer) {
          // 답변 메시지 추가
          historyMessages.push({
            id: `answer-${answer.question_id}`,
            type: 'answer',
            content: answer.user_answer,
            timestamp: new Date(answer.submitted_at),
            question_id: answer.question_id
          })
          
          // 피드백 메시지 추가 (있는 경우)
          if (answer.feedback && answer.feedback.score) {
            historyMessages.push({
              id: `feedback-${answer.question_id}`,
              type: 'feedback', 
              content: answer.feedback.message || '피드백이 생성되었습니다.',
              timestamp: new Date(answer.feedback.created_at || answer.submitted_at),
              question_id: answer.question_id,
              feedback: {
                score: answer.feedback.score,
                message: answer.feedback.message,
                feedback_type: answer.feedback.feedback_type || 'general',
                details: answer.feedback.details,
                keywords_found: answer.feedback.keywords_found || [],
                keywords_missing: answer.feedback.keywords_missing || [],
                suggestions: answer.feedback.suggestions || [],
                technical_accuracy: answer.feedback.technical_accuracy || answer.feedback.details
              }
            })
          }
        }
      })
      
      // 대화 메시지 추가 (최신순으로)
      data.conversations.forEach((conv: any) => {
        if (conv.type === 'user') {
          historyMessages.push({
            id: `conversation-user-${conv.id}`,
            type: 'answer',
            content: conv.content,
            timestamp: new Date(conv.timestamp),
            question_id: conv.question_id
          })
        } else if (conv.type === 'ai') {
          historyMessages.push({
            id: `conversation-ai-${conv.id}`,
            type: 'system',
            content: conv.content,
            timestamp: new Date(conv.timestamp),
            question_id: conv.question_id
          })
        }
      })
      
      // 시간순으로 정렬
      historyMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      
      // 현재 질문 인덱스 계산 (답변된 질문 수 기준)
      const answeredCount = data.answers.length
      const calculatedCurrentIndex = Math.min(answeredCount, questionsList.length - 1)
      setCurrentQuestionIndex(calculatedCurrentIndex)
      
      console.log('[HISTORY] 전체 히스토리 로드 완료:', {
        answersCount: data.answers.length,
        conversationsCount: data.conversations.length,
        messagesCount: historyMessages.length,
        currentQuestionIndex: calculatedCurrentIndex
      })
      
      return { historyMessages, answeredCount, calculatedCurrentIndex }
      
    } catch (error) {
      console.error('[ERROR] 세션 히스토리 로딩 실패:', error)
      // 에러 발생 시 기본 상태로 시작
      setMessages(prev => [...prev, {
        id: 'history-error',
        type: 'system',
        content: '세션 기록을 복원하는 중 오류가 발생했습니다. 새로 시작합니다.',
        timestamp: new Date()
      }])
      return null
    }
  }

  const loadInterview = async () => {
    debugLog.info('interview', 'loadInterview 함수 시작');
    
    setLoadingStates({ session: true, questions: true })
    
    try {
      debugLog.info('api', '면접 세션 및 질문 데이터 로딩 시작');
      // 병렬 API 호출로 성능 개선
      const [sessionResponse, questionsResponse] = await Promise.all([
        fetch(`/api/v1/interview/session/${interviewId}`),
        fetch(`/api/v1/interview/session/${interviewId}/questions`)
      ])
      
      console.log('[API] API 응답 상태:', {
        session: sessionResponse.status,
        questions: questionsResponse.status
      });
      
      // 세션 데이터 확인
      setLoadingStates(prev => ({ ...prev, session: false }))
      
      if (!sessionResponse.ok) {
        if (sessionResponse.status === 404) {
          // 404 에러에 대한 사용자 친화적 처리
          setMessages([{
            id: 'session-not-found',
            type: 'system',
            content: '면접 세션을 찾을 수 없습니다. 세션이 만료되었거나 시스템이 업데이트되었을 수 있습니다. 새로운 면접을 시작해주세요.',
            timestamp: new Date()
          }])
          
          setTimeout(() => {
            navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard', { 
              state: { 
                message: '이전 면접 세션이 만료되었습니다. 새로운 분석을 시작해주세요.',
                type: 'warning'
              }
            })
          }, 3000)
          return
        }
        throw new Error(`면접 세션을 불러오는데 실패했습니다. (${sessionResponse.status})`)
      }
      
      if (!questionsResponse.ok) {
        if (questionsResponse.status === 404) {
          // 질문 데이터를 찾을 수 없는 경우
          setMessages([{
            id: 'questions-not-found',
            type: 'system',
            content: '면접 질문을 찾을 수 없습니다. 분석 데이터가 손실되었거나 시스템이 업데이트되었을 수 있습니다.',
            timestamp: new Date()
          }])
          
          setTimeout(() => {
            navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard', { 
              state: { 
                message: '면접 질문 데이터를 찾을 수 없습니다. 새로운 분석을 시작해주세요.',
                type: 'warning'
              }
            })
          }, 3000)
          return
        }
        throw new Error(`면접 질문을 불러오는데 실패했습니다. (${questionsResponse.status})`)
      }
      
      setLoadingStates(prev => ({ ...prev, questions: false }))

      console.log('[PARSE] JSON 파싱 시작');
      const [sessionResult, questionsResult] = await Promise.all([
        sessionResponse.json(),
        questionsResponse.json()
      ])
      
      console.log('[RESULT] API 결과:', {
        sessionSuccess: sessionResult.success,
        questionsSuccess: questionsResult.success,
        sessionData: sessionResult.data,
        questionsData: questionsResult.data
      });

      if (!sessionResult.success || !questionsResult.success) {
        throw new Error(sessionResult.message || questionsResult.message || '면접 데이터를 불러오는데 실패했습니다.')
      }
        
      console.log('[SUCCESS] API 결과 검증 통과, 상태 업데이트 시작');
      
      const sessionData = sessionResult.data
      const questionsData = questionsResult.data.questions
      
      // 중복 제거를 위한 고유 질문 필터링
      const uniqueQuestionsData = questionsData.filter((question: any, index: number, array: any[]) => 
        array.findIndex(q => q.id === question.id) === index
      );
      
      console.log('[DEDUP] 원본 질문 수:', questionsData.length, '중복 제거 후:', uniqueQuestionsData.length);
      
      // 질문 데이터 형식 변환 (context 객체를 문자열로 변환)
      const transformedQuestions = uniqueQuestionsData.map((q: any) => ({
        id: q.id,
        question: q.question,
        question_headline: q.question_headline,
        question_details_markdown: q.question_details_markdown,
        question_has_details: q.question_has_details,
        category: q.category,
        difficulty: q.difficulty,
        context: typeof q.context === 'object' ? 
          (q.context?.original_data?.context || q.context?.context || JSON.stringify(q.context)) : 
          q.context,
        parent_question_id: q.context?.original_data?.parent_question_id,
        sub_question_index: q.context?.original_data?.sub_question_index,
        total_sub_questions: q.context?.original_data?.total_sub_questions,
        is_compound_question: q.context?.original_data?.is_compound_question
      }))
      
      setInterview(sessionData)
      setQuestions(transformedQuestions)
      
      console.log('[UPDATE] 상태 업데이트 완료');
      
      // 세션 히스토리 데이터 로딩
      const historyResult = await loadSessionHistory(transformedQuestions, sessionData);
      
      // 현재 질문 인덱스 결정 (히스토리에서 계산된 값 우선 사용)
      let actualCurrentIndex = questionsResult.data.current_question_index || 0
      if (historyResult?.calculatedCurrentIndex !== undefined) {
        actualCurrentIndex = historyResult.calculatedCurrentIndex
      }
      
      // 세션 상태에 따른 메시지 설정
      const currentQuestion = transformedQuestions[actualCurrentIndex]
      const isResuming = historyResult && historyResult.historyMessages.length > 0
      
      console.log('[QUESTION] 현재 질문 정보:', {
        index: actualCurrentIndex,
        question: currentQuestion,
        isResuming: isResuming,
        totalQuestions: transformedQuestions.length
      });
      
      // 메시지 설정
      const welcomeMessages: Message[] = []
      
      if (isResuming) {
        // 기존 세션 복원
        welcomeMessages.push({
          id: 'session-restored',
          type: 'system', 
          content: `이전 면접 세션이 복원되었습니다. (${historyResult.answeredCount}/${transformedQuestions.length} 질문 완료)`,
          timestamp: new Date()
        })
        
        // 히스토리 메시지 추가
        welcomeMessages.push(...historyResult.historyMessages)
        
        // 현재 진행 상황 표시
        if (actualCurrentIndex < transformedQuestions.length) {
          welcomeMessages.push({
            id: 'current-progress',
            type: 'system',
            content: `📍 현재 진행상황: ${actualCurrentIndex + 1}/${transformedQuestions.length} (${Math.round(((actualCurrentIndex + 1) / transformedQuestions.length) * 100)}%)`,
            timestamp: new Date()
          })
          
          // 현재/다음 질문 표시
          if (currentQuestion) {
            welcomeMessages.push({
              id: `question-${currentQuestion.id}`,
              type: 'question',
              content: currentQuestion.question,
              timestamp: new Date(),
              question_id: currentQuestion.id
            })
          }
        } else {
          // 모든 질문 완료
          welcomeMessages.push({
            id: 'all-completed',
            type: 'system',
            content: '모든 질문이 완료되었습니다! 면접을 종료하거나 답변을 검토해보세요.',
            timestamp: new Date()
          })
        }
      } else {
        // 새로운 면접 시작
        welcomeMessages.push({
          id: 'welcome',
          type: 'system',
          content: '모의면접을 시작합니다! 편안하게 답변해주세요.',
          timestamp: new Date()
        })
        
        if (transformedQuestions.length > 0) {
          welcomeMessages.push({
            id: 'interview-info',
            type: 'system',
            content: `총 ${transformedQuestions.length}개의 질문이 준비되었습니다.`,
            timestamp: new Date()
          })
          
          // 첫 번째 질문 표시
          if (currentQuestion) {
            welcomeMessages.push({
              id: `question-${currentQuestion.id}`,
              type: 'question',
              content: currentQuestion.question,
              timestamp: new Date(),
              question_id: currentQuestion.id
            })
          }
        }
      }
      
      setMessages(welcomeMessages)
      setCurrentQuestionIndex(actualCurrentIndex)
      
      console.log('[DEBUG] loadInterview 완료 - actualCurrentIndex:', actualCurrentIndex);
      
    } catch (error) {
      console.error('[ERROR] Error loading interview:', error)
      const errorMessage = error instanceof Error ? error.message : '면접 데이터를 불러오는데 실패했습니다.'
      
      setMessages([{
        id: 'load-error',
        type: 'system',
        content: `ERROR: ${errorMessage}`,
        timestamp: new Date()
      }])
      
      setTimeout(() => {
        navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard')
      }, 3000)
      
    } finally {
      console.log('[UPDATE] setIsLoading(false) 설정');
      setIsLoading(false)
      setLoadingStates({ session: false, questions: false })
    }
  }

  const submitAnswer = async () => {
    console.log('[SUBMIT] submitAnswer 함수 실행됨');
    console.log('[SUBMIT] currentAnswer:', currentAnswer);
    console.log('[SUBMIT] currentAnswer.length:', currentAnswer.length);
    console.log('[SUBMIT] currentAnswer.trim():', currentAnswer.trim());
    console.log('[SUBMIT] currentAnswer.trim().length:', currentAnswer.trim().length);
    console.log('[SUBMIT] conversationMode:', conversationMode);
    console.log('[SUBMIT] isSubmitting:', isSubmitting);
    
    // 이미 제출 중인 경우 중복 실행 방지
    if (isSubmitting) {
      console.log('[BLOCK] 이미 제출 중 - 중복 실행 방지');
      return;
    }
    
    if (!currentAnswer.trim()) {
      console.log('[ERROR] currentAnswer가 비어있음 - 제출 중단');
      alert('답변을 입력해주세요!');
      return;
    }

    // 즉시 제출 상태로 설정하여 중복 실행 방지
    console.log('[LOCK] 제출 상태 잠금 설정');
    setIsSubmitting(true);

    // 대화 모드인 경우 대화 처리
    if (conversationMode) {
      return await handleConversation();
    }

    // 일반 면접 답변 처리
    console.log('[SUBMIT] interview:', interview);
    console.log('[SUBMIT] interviewId:', interviewId);
    console.log('[SUBMIT] questions.length:', questions.length);
    if (!interview) {
      console.log('[ERROR] interview 객체가 없음');
      setIsSubmitting(false);
      return;
    }
    if (!interviewId) {
      console.log('[ERROR] interviewId가 없음');
      setIsSubmitting(false);
      return;
    }

    console.log('[SUCCESS] 모든 조건 통과, 답변 제출 시작');
    
    try {
      // 현재 질문 찾기 (progress 대신 실제 currentQuestionIndex 사용)
      const currentQuestion = questions[currentQuestionIndex]
      console.log('[QUESTION] currentQuestion:', currentQuestion);
      console.log('[QUESTION] currentQuestionIndex:', currentQuestionIndex);
      
      if (!currentQuestion) {
        console.log('[ERROR] currentQuestion이 없음 - currentQuestionIndex:', currentQuestionIndex);
        console.log('[ERROR] questions 배열 길이:', questions.length);
        throw new Error('현재 질문을 찾을 수 없습니다. 페이지를 새로고침해보세요.');
      }
      
      // 답변 메시지 추가
      const answerMessageId = `answer-${Date.now()}`;
      const answerMessage: Message = {
        id: answerMessageId,
        type: 'answer',
        content: currentAnswer,
        timestamp: new Date(),
        question_id: currentQuestion.id
      }
      
      console.log('[MESSAGE] 답변 메시지 추가:', answerMessage);
      setMessages(prev => [...prev, answerMessage])
      
      // REST API로 답변 전송
      const requestBody = {
        interview_id: interviewId,
        question_id: currentQuestion.id,
        answer: currentAnswer,
        time_taken: 60 // 임시값
      };
      
      console.log('[API] API 요청 시작:', requestBody);
      
      const response = await fetch('/api/v1/interview/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      })
      
      console.log('[API] API 응답 상태:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.log('[ERROR] API 응답 에러:', errorText);
        throw new Error(`답변 제출에 실패했습니다. (${response.status})`);
      }

      const result = await response.json()
      console.log('[SUCCESS] API 응답 결과:', result);
      
      if (result.success) {
        console.log('[SUCCESS] 답변 제출 성공');
        
        // 피드백 처리 - 답변 메시지에 피드백 데이터 추가
        if (result.data.feedback) {
          console.log('[FEEDBACK] 피드백 데이터 수신:', result.data.feedback);
          console.log('[FEEDBACK] overall_score:', result.data.feedback.overall_score);
          console.log('[FEEDBACK] 전체 구조:', JSON.stringify(result.data.feedback, null, 2));
          
          // 방금 추가한 답변 메시지에 피드백 추가
          setMessages(prev => prev.map(msg => {
            if (msg.id === answerMessageId) {
              console.log('[FEEDBACK_UPDATE] 메시지 업데이트:', {
                messageId: msg.id,
                feedbackData: result.data.feedback,
                overallScore: result.data.feedback.overall_score
              });
              return {
                ...msg,
                feedback: result.data.feedback
              };
            }
            return msg;
          }));

          // 자동 대화 모드 시작 기능 제거됨 - 사용자가 현재 질문에 집중할 수 있도록 함
        }
        
        // 다음 질문으로 이동하거나 완료 처리
        if (result.data.is_completed) {
          console.log('[COMPLETE] 면접 완료');
          setInterview(prev => prev ? { ...prev, status: 'completed' } : null)
          setMessages(prev => [...prev, {
            id: 'completed',
            type: 'system',
            content: '모든 질문이 완료되었습니다! 수고하셨습니다. 결과를 확인해보세요.',
            timestamp: new Date()
          }])
        } else {
          console.log('[NEXT] 다음 질문으로 이동 준비');
          
          // 피드백 점수에 따른 안내 메시지
          if (result.data.feedback) {
            const score = result.data.feedback.score
            let guidanceMessage = ''
            
            if (score >= 8.0) {
              guidanceMessage = '훌륭한 답변입니다! 다음 질문으로 자동 진행됩니다.'
              
              // 높은 점수면 자동으로 다음 질문
              setTimeout(async () => {
                await loadInterview();
              }, 2500);
              
            } else if (score >= 6.0) {
              guidanceMessage = '좋은 답변입니다. 추가 질문이 있으면 언제든 물어보세요. "다음 질문"을 입력하면 계속 진행할 수 있습니다.'
            } else {
              guidanceMessage = '답변에 대해 더 자세히 알아보고 싶다면 추가 질문을 해보세요. 준비가 되면 "다음 질문"을 입력하세요.'
            }
            
            if (guidanceMessage) {
              setMessages(prev => [...prev, {
                id: `guidance-${Date.now()}`,
                type: 'system',
                content: guidanceMessage,
                timestamp: new Date()
              }])
            }
          } else {
            // 피드백이 없는 경우 기본 안내
            setMessages(prev => [...prev, {
              id: `next-guidance-${Date.now()}`,
              type: 'system',
              content: 'NOTE 답변이 저장되었습니다. "다음 질문"을 입력하여 계속 진행하거나, 이 문제에 대해 더 질문해보세요.',
              timestamp: new Date()
            }])
          }
        }
        
        // 성공적으로 처리된 경우에만 답변 입력창 초기화
        console.log('[CLEAR] 답변 입력창 초기화');
        setCurrentAnswer('');
        
        // 답변 제출 후 textarea 상단으로 스크롤
        setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.scrollTop = 0;
          }
        }, 100);
      } else {
        console.log('[ERROR] API 호출은 성공했지만 result.success가 false');
        throw new Error(result.message || '답변 처리에 실패했습니다.');
      }
      
    } catch (error) {
      console.error('[ERROR] Error submitting answer:', error)
      const errorMessage = error instanceof Error ? error.message : '답변 제출에 실패했습니다.';
      
      // 사용자 친화적인 에러 메시지 표시
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        type: 'system',
        content: `ERROR: ${errorMessage}. 잠시 후 다시 시도해주세요.`,
        timestamp: new Date()
      }]);
      
      // 답변 내용은 유지 (사용자가 다시 입력하지 않도록)
      console.log('[PRESERVE] 오류 발생으로 답변 내용 유지');
      
    } finally {
      console.log('[UPDATE] isSubmitting을 false로 설정');
      setIsSubmitting(false)
    }
  }

  const finishInterview = async () => {
    if (!interviewId || isFinishingInterview) return

    setIsFinishingInterview(true)
    try {
      const response = await fetch(`/api/v1/interview/${interviewId}/finish`, {
        method: 'POST'
      })
      
      if (response.ok) {
        setIsFinishConfirmOpen(false)
        navigate('/reports')
      } else {
        throw new Error('면접 종료에 실패했습니다.')
      }
    } catch (error) {
      console.error('Error finishing interview:', error)
      setMessages(prev => [...prev, {
        id: `finish-error-${Date.now()}`,
        type: 'system',
        content: 'ERROR: 면접 종료 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.',
        timestamp: new Date()
      }])
    } finally {
      setIsFinishingInterview(false)
    }
  }

  const requestFinishInterview = () => {
    if (interview?.status === 'completed' || isFinishingInterview) {
      return
    }
    setIsHeaderSettingsOpen(false)
    setIsFinishConfirmOpen(true)
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const navigateQuestion = (direction: number) => {
    if (!questions.length) return
    
    const newIndex = Math.max(0, Math.min(questions.length - 1, currentQuestionIndex + direction))
    setCurrentQuestionIndex(newIndex)
  }

  // 대화 모드 종료
  const endConversation = () => {
    setConversationMode(null);
    setMessages(prev => [...prev, {
      id: `conversation-end-${Date.now()}`,
      type: 'system',
      content: '[CONVERSATION] 개별 상담을 종료합니다.',
      timestamp: new Date()
    }]);
  }

  // 대화 처리
  const handleConversation = async () => {
    if (!conversationMode) return;

    try {
      setIsSubmitting(true);
      
      // "다음 질문" 키워드 체크
      const isNextQuestionRequest = /다음\s*질문|다음으로|넘어가|다음|next/i.test(currentAnswer.trim());
      
      if (isNextQuestionRequest) {
        // 다음 질문으로 이동
        setMessages(prev => [...prev, {
          id: `next-question-${Date.now()}`,
          type: 'answer',
          content: currentAnswer,
          timestamp: new Date()
        }, {
          id: `next-question-response-${Date.now()}`,
          type: 'system',
          content: '네, 다음 질문으로 넘어가겠습니다!',
          timestamp: new Date()
        }]);
        
        // 대화 모드 종료
        setConversationMode(null);
        
        // 다음 질문 로드
        setTimeout(async () => {
          await loadInterview();
        }, 1500);
        
        setCurrentAnswer('');
        return;
      }
      
      // 사용자 질문 메시지 추가
      const userQuestion: Message = {
        id: `conversation-question-${Date.now()}`,
        type: 'answer',
        content: currentAnswer,
        timestamp: new Date(),
        question_id: conversationMode.questionId
      };
      
      setMessages(prev => [...prev, userQuestion]);
      
      // 백엔드 대화 API 호출
      const response = await fetch('/api/v1/interview/conversation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          interview_id: interviewId,
          question_id: conversationMode.questionId,
          original_answer: conversationMode.originalAnswer,
          conversation_question: currentAnswer
        })
      });
      
      if (!response.ok) {
        throw new Error(`대화 요청에 실패했습니다. (${response.status})`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        // AI 응답 메시지 추가
        const aiResponse: Message = {
          id: `conversation-answer-${Date.now()}`,
          type: 'system',
          content: result.data.response,
          timestamp: new Date()
        };
        
        setMessages(prev => [...prev, aiResponse]);
      } else {
        throw new Error(result.message || '대화 처리에 실패했습니다.');
      }
      
      setCurrentAnswer('');
      
    } catch (error) {
      console.error('[ERROR] 대화 처리 중 오류:', error);
      
      // 에러 메시지 표시
      const errorResponse: Message = {
        id: `conversation-error-${Date.now()}`,
        type: 'system',
        content: `[ERROR] ${error instanceof Error ? error.message : '대화 처리 중 오류가 발생했습니다.'}`,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsSubmitting(false);
    }
  }

  const goToQuestion = (index: number) => {
    if (index >= 0 && index < questions.length) {
      setCurrentQuestionIndex(index)
    }
  }

  const saveCurrentAnswer = () => {
    const currentQ = questions[currentQuestionIndex]
    if (currentQ && interviewId && currentAnswer) {
      const savedKey = `interview_${interviewId}_${currentQ.id}`
      localStorage.setItem(savedKey, currentAnswer)
      setLastSaved(new Date())
    }
  }

  const getProgressText = (): string => {
    const currentQ = questions[currentQuestionIndex]
    if (currentQ?.parent_question_id && currentQ.sub_question_index && currentQ.total_sub_questions) {
      const groupQuestions = questions.filter(q => q.parent_question_id === currentQ.parent_question_id)
      const groupIndex = Math.floor(currentQuestionIndex / groupQuestions.length) + 1
      const totalGroups = Math.ceil(questions.length / groupQuestions.length)
      return `그룹 ${groupIndex}/${totalGroups} - ${currentQ.sub_question_index}/${currentQ.total_sub_questions}`
    }
    return `질문 ${currentQuestionIndex + 1} / ${questions.length}`
  }

  const isLastQuestionInGroup = (questionIndex: number): boolean => {
    const question = questions[questionIndex]
    if (!question?.parent_question_id) return true
    
    const groupQuestions = questions.filter(q => q.parent_question_id === question.parent_question_id)
    return question.sub_question_index === groupQuestions.length
  }

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const getCategoryThemeClass = (category: string): string => {
    switch (category?.toLowerCase()) {
      case 'technical': return 'category-theme-technical'
      case 'tech_stack': return 'category-theme-tech-stack'
      case 'architecture': return 'category-theme-architecture'
      case 'algorithm': return 'category-theme-algorithm'
      case 'database': return 'category-theme-database'
      case 'frontend': return 'category-theme-frontend'
      case 'backend': return 'category-theme-backend'
      case 'devops': return 'category-theme-devops'
      case 'testing': return 'category-theme-testing'
      case 'security': return 'category-theme-security'
      default: return 'category-theme-default'
    }
  }

  const getCategoryIcon = (category: string): React.ReactNode => {
    const themeClass = getCategoryThemeClass(category)

    switch (category?.toLowerCase()) {
      case 'technical': return <Code className={`icon category-icon ${themeClass}`} />
      case 'tech_stack': return <Layers className={`icon category-icon ${themeClass}`} />
      case 'architecture': return <Monitor className={`icon category-icon ${themeClass}`} />
      case 'algorithm': return <Zap className={`icon category-icon ${themeClass}`} />
      case 'database': return <Database className={`icon category-icon ${themeClass}`} />
      case 'frontend': return <Palette className={`icon category-icon ${themeClass}`} />
      case 'backend': return <Server className={`icon category-icon ${themeClass}`} />
      case 'devops': return <Terminal className={`icon category-icon ${themeClass}`} />
      case 'testing': return <Bug className={`icon category-icon ${themeClass}`} />
      case 'security': return <Shield className={`icon category-icon ${themeClass}`} />
      default: return <HelpCircle className={`icon category-icon ${themeClass}`} />
    }
  }

  const getDifficultyClass = (difficulty: string): string => {
    switch (difficulty?.toLowerCase()) {
      case 'easy': return 'difficulty-easy'
      case 'medium': return 'difficulty-medium'
      case 'hard': return 'difficulty-hard'
      default: return 'difficulty-default'
    }
  }

  if (isLoading) {
    return (
      <div className="interview-page v2-root interview-v2">
        <div className="interview-loading">
          <div className="interview-spinner-large"></div>
          <p>면접을 준비하고 있습니다...</p>
          <div className="loading-progress">
            <div className="progress-item">
              <span className={loadingStates.session ? 'loading' : 'complete'}>
                {loadingStates.session ? '[LOADING]' : '[DONE]'} 면접 세션 정보
              </span>
            </div>
            <div className="progress-item">
              <span className={loadingStates.questions ? 'loading' : 'complete'}>
                {loadingStates.questions ? '[LOADING]' : '[DONE]'} 면접 질문 데이터
              </span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!interview) {
    return (
      <div className="interview-page v2-root interview-v2">
        <div className="interview-error">
          <h2>면접을 찾을 수 없습니다</h2>
          <button onClick={() => navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard')}>대시보드로 돌아가기</button>
        </div>
      </div>
    )
  }

  const currentQuestion = questions[currentQuestionIndex]
  const currentQuestionDisplay = currentQuestion
    ? formatQuestionForDisplay({
        question: currentQuestion.question,
        question_headline: currentQuestion.question_headline,
        question_details_markdown: currentQuestion.question_details_markdown,
        question_has_details: currentQuestion.question_has_details
      })
    : null
  const progressPercentage = questions.length > 0
    ? Math.round(((currentQuestionIndex + 1) / questions.length) * 100)
    : 0
  const estimatedRemainingMinutes = Math.max(1, Math.ceil(timeRemaining / 60))
  const timerUrgencyClass =
    timeRemaining <= 5 * 60
      ? 'timer-v2--critical'
      : timeRemaining <= 15 * 60
        ? 'timer-v2--warning'
        : ''

  const headerContent = (
    <>
      <div className="v2-header-left">
        <MessageCircle className="v2-icon-sm" />
        <span className="v2-header-title">모의면접 진행중</span>
        <span className="v2-badge v2-badge-arch">{getProgressText()}</span>
      </div>
      <div className="v2-header-right">
        <div className={`timer timer-v2 ${timerUrgencyClass}`.trim()}>
          <Clock className="v2-icon-xs" />
          <span className="timer-value">{formatTime(timeRemaining)}</span>
        </div>
        <div
          className={`connection-status connection-status-v2 connection-status-v2--compact ${wsConnected ? 'connected' : 'disconnected'}`}
          title={wsConnected ? '연결됨' : '연결 끊김'}
          aria-label={wsConnected ? '연결됨' : '연결 끊김'}
        >
          <span className="status-dot"></span>
          <span className="v2-sr-only">{wsConnected ? '연결됨' : '연결 끊김'}</span>
        </div>
        <select
          className="v2-select interview-font-size-select"
          value={fontSize}
          onChange={(e) => setFontSize(e.target.value)}
          title="폰트 크기"
        >
          <option value="small">작게</option>
          <option value="medium">보통</option>
          <option value="large">크게</option>
        </select>
        <button
          className={`setting-btn interview-focus-toggle ${isFocusMode ? 'active' : ''}`}
          onClick={() => setIsFocusMode((prev) => !prev)}
          title={isFocusMode ? '사이드바 표시' : '집중 모드'}
        >
          <Monitor className="v2-icon-sm" />
          <span className="v2-sr-only">{isFocusMode ? '사이드바 표시' : '집중 모드'}</span>
        </button>
        <div className="interview-header-settings" ref={headerSettingsRef}>
          <button
            className={`setting-btn interview-settings-toggle ${isHeaderSettingsOpen ? 'active' : ''}`}
            onClick={() => setIsHeaderSettingsOpen((prev) => !prev)}
            title="면접 설정"
            aria-label="면접 설정"
            aria-expanded={isHeaderSettingsOpen}
          >
            <Settings className="v2-icon-sm" />
          </button>
          {isHeaderSettingsOpen && (
            <div className="interview-settings-popover">
              <button
                type="button"
                className="interview-settings-item"
                onClick={() => {
                  setIsFocusMode((prev) => !prev)
                  setIsHeaderSettingsOpen(false)
                }}
              >
                {isFocusMode ? '사이드바 표시' : '집중 모드'}
              </button>
              <button
                type="button"
                className="interview-settings-item interview-settings-item--danger"
                onClick={requestFinishInterview}
                disabled={interview.status === 'completed' || isFinishingInterview}
              >
                {isFinishingInterview ? '종료 중...' : '면접 종료'}
              </button>
            </div>
          )}
        </div>
        <button
          className={`setting-btn ${isDarkMode ? 'active' : ''}`}
          onClick={() => setIsDarkMode(!isDarkMode)}
          title="다크 모드 (Ctrl+D)"
        >
          {isDarkMode ? <Sun className="v2-icon-sm" /> : <Moon className="v2-icon-sm" />}
        </button>
      </div>
    </>
  )

  const sidebarContent = (
    <div className="interview-v2-sidebar">
      <div className="v2-sidebar-section">
        <div className="v2-sidebar-section-header">
          <FileText className="v2-icon-xs" />
          <span className="v2-label">면접 진행 상황</span>
          <span className="v2-badge v2-badge-arch v2-progress-badge">
            {questions.length > 0 ? `${currentQuestionIndex + 1}/${questions.length}` : '0/0'}
          </span>
        </div>
        <div className="v2-sidebar-section-body">
          <div className="questions-list questions-list-v2">
            {questions.map((question, index) => {
              const previewText = buildQuestionPreviewText(
                {
                  question: question.question,
                  question_headline: question.question_headline,
                  question_details_markdown: question.question_details_markdown,
                  question_has_details: question.question_has_details
                },
                56
              )

              return (
                <div
                  key={question.id}
                  className={`question-item ${
                    index === currentQuestionIndex ? 'current' :
                    index < currentQuestionIndex ? 'completed' : 'pending'
                  }`}
                  onClick={() => goToQuestion(index)}
                >
                  <div className="question-number">Q{index + 1}</div>
                  <div className="question-preview">
                    <span className="question-preview-text">
                      {previewText || '질문 미리보기를 불러오는 중...'}
                    </span>
                    <div className="question-badges">
                      <span className={`mini-category ${getCategoryThemeClass(question.category)}`}>{getCategoryIcon(question.category)}</span>
                      <span className={`mini-difficulty ${getDifficultyClass(question.difficulty)}`}>
                        {question.difficulty}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="v2-sidebar-section">
        <div className="v2-sidebar-section-header v2-sidebar-section-header--collapsible">
          <Lightbulb className="v2-icon-xs" />
          <span className="v2-label">면접 팁</span>
          <button
            type="button"
            className="tips-toggle-btn"
            onClick={() => setIsTipsCollapsed((prev) => !prev)}
            aria-label={isTipsCollapsed ? '면접 팁 펼치기' : '면접 팁 접기'}
            aria-expanded={!isTipsCollapsed}
          >
            <ChevronDown className={`v2-icon-xs tips-toggle-icon ${isTipsCollapsed ? 'collapsed' : ''}`} />
          </button>
        </div>
        {!isTipsCollapsed && (
          <div className="v2-sidebar-section-body">
            <ul className="interview-tips">
              <li>차분하게 생각한 후 답변하세요</li>
              <li>구체적인 예시를 들어 설명하세요</li>
              <li>모르는 것은 솔직히 말하세요</li>
              <li>시간을 충분히 활용하세요</li>
            </ul>
          </div>
        )}
      </div>
      <div className="v2-sidebar-section">
        <div className="v2-sidebar-section-header">
          <Clock className="v2-icon-xs" />
          <span className="v2-label">진행 요약</span>
        </div>
        <div className="v2-sidebar-section-body interview-sidebar-summary">
          <div className="interview-progress-track" aria-hidden="true">
            <span className="interview-progress-fill" style={{ width: `${progressPercentage}%` }} />
          </div>
          <div className="interview-sidebar-summary-row">
            <span>진행률</span>
            <strong>{progressPercentage}%</strong>
          </div>
          <div className="interview-sidebar-summary-row">
            <span>예상 남은 시간</span>
            <strong>약 {estimatedRemainingMinutes}분</strong>
          </div>
          <button
            type="button"
            className="finish-interview-btn"
            onClick={requestFinishInterview}
            disabled={interview.status === 'completed' || isFinishingInterview}
          >
            {isFinishingInterview ? '종료 중...' : '면접 종료'}
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className={`interview-page v2-root interview-v2 ${isDarkMode ? 'dark-mode' : ''} ${isFocusMode ? 'focus-mode' : ''} font-size-${fontSize}`}>
      <AppShellV2
        header={headerContent}
        sidebar={isFocusMode ? <div className="interview-v2-sidebar-empty">집중 모드</div> : sidebarContent}
        sidebarWidth={sidebarWidth}
        isResizing={isResizingSidebar}
        onResizeStart={startSidebarResize}
        onResizeReset={resetSidebarWidth}
        className="interview-v2-shell v2-tone-709"
      >
        <div className="interview-content interview-v2-main-content">
          <div className="question-container" ref={questionContainerRef}>
            {currentQuestion && (
              <div className="current-question">
                <div className="interview-question-header">
                  <div className="interview-question-meta">
                    <span className="interview-question-number">
                      {currentQuestion.parent_question_id && currentQuestion.sub_question_index
                        ? `Q${currentQuestion.sub_question_index}`
                        : `Q${currentQuestionIndex + 1}`}
                    </span>
                    {getCategoryIcon(currentQuestion.category)}
                    <span className="interview-category-name">{currentQuestion.category}</span>
                    <span
                      className={`interview-difficulty-badge ${getDifficultyClass(currentQuestion.difficulty)}`}
                    >
                      {currentQuestion.difficulty}
                    </span>
                  </div>
                  <div className="interview-question-navigation">
                    <button
                      className="interview-nav-btn prev"
                      onClick={() => navigateQuestion(-1)}
                      disabled={currentQuestionIndex === 0}
                      title="이전 질문 (Ctrl+←)"
                    >
                      <ChevronLeft className="v2-icon-sm interview-nav-icon interview-nav-icon--left" />
                      이전
                    </button>
                    <button
                      className="interview-nav-btn next"
                      onClick={() => navigateQuestion(1)}
                      disabled={currentQuestionIndex === questions.length - 1}
                      title="다음 질문 (Ctrl+→)"
                    >
                      {isLastQuestionInGroup(currentQuestionIndex) ? '다음 그룹' : '다음'}
                      <ChevronRight className="v2-icon-sm interview-nav-icon interview-nav-icon--right" />
                    </button>
                  </div>
                </div>
                <div className="interview-question-content">
                  <div className="interview-question-text">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p className="markdown-paragraph">{children}</p>,
                        strong: ({ children }) => <strong className="markdown-strong">{children}</strong>,
                        code: ({ children }) => <code className="markdown-code">{children}</code>,
                        pre: ({ children }) => <pre className="markdown-pre">{children}</pre>
                      }}
                    >
                      {currentQuestionDisplay?.headline || currentQuestion.question}
                    </ReactMarkdown>
                  </div>
                  {currentQuestionDisplay?.hasDetails && currentQuestionDisplay.detailsMarkdown && (
                    <div className="interview-question-details">
                      <span className="interview-question-details-label">비교/확장 포인트</span>
                      <div className="interview-question-details-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {currentQuestionDisplay.detailsMarkdown}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                  {currentQuestion.context && (
                    <div className="interview-question-context">
                      <Lightbulb className="v2-icon-sm interview-question-context-icon interview-question-context-icon--inline" />
                      {currentQuestion.context}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="answer-history">
              {messages.filter(msg => msg.type === 'answer' && msg.question_id === currentQuestion?.id).map((message) => (
                <div key={message.id} className={`answer-item ${message.type === 'system' ? 'system-message' : ''}`}>
                  <div className="answer-header">
                    <span className="answer-label">
                      {message.type === 'system' ? 'AI 면접관' : '내 답변'}
                    </span>
                    <span className="answer-time">
                      {message.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="answer-content">
                    {message.content}
                  </div>

                  {message.type === 'answer' && message.feedback && (
                    <div className="answer-feedback-section">
                      {message.feedback.is_conversation ? (
                        <div className="conversation-feedback">
                          <div className="interview-feedback-header">
                            <span className="interview-feedback-label">AI 응답</span>
                          </div>
                          <div className="interview-feedback-message">
                            {message.feedback.feedback || message.feedback.message}
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="interview-feedback-header">
                            <span className="interview-feedback-label">AI 피드백</span>
                            <span className="interview-feedback-score">
                              {(message.feedback?.overall_score || message.feedback?.score || 0)}/10
                            </span>
                          </div>
                          <div className="interview-feedback-message">
                            {message.feedback.feedback || message.feedback.message}
                          </div>
                          {message.feedback.suggestions && (
                            <div className="interview-feedback-suggestions">
                              <div className="interview-suggestions-title">개선 제안:</div>
                              <ul className="interview-suggestions-list">
                                {message.feedback.suggestions.map((suggestion, index) => (
                                  <li key={index}>{suggestion}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {conversationMode && (
              <div className="conversation-area">
                <div className="conversation-header">[CHAT] AI 멘토와 대화</div>
                {messages.filter(msg =>
                  msg.type === 'system' &&
                  msg.question_id === currentQuestion?.id && (
                    msg.content.includes('다음 질문으로 넘어가겠습니다') ||
                    msg.content.includes('좋은 질문이네요') ||
                    msg.content.includes('답변드리겠습니다') ||
                    msg.content.includes('안녕하세요')
                  )
                ).map((message) => (
                  <div key={message.id} className="conversation-message ai-message">
                    <div className="message-header">
                      <span className="message-label">AI 멘토</span>
                      <span className="message-time">{message.timestamp.toLocaleTimeString()}</span>
                    </div>
                    <div className="message-content">{message.content}</div>
                  </div>
                ))}

                {messages.filter(msg =>
                  msg.type === 'answer' && conversationMode &&
                  msg.question_id === conversationMode.questionId &&
                  msg.question_id === currentQuestion?.id &&
                  msg.content !== conversationMode.originalAnswer
                ).map((message) => (
                  <div key={message.id} className="conversation-message user-message">
                    <div className="message-header">
                      <span className="message-label">내 질문</span>
                      <span className="message-time">{message.timestamp.toLocaleTimeString()}</span>
                    </div>
                    <div className="message-content">{message.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {currentFeedback && (
            <AnswerFeedback
              feedback={currentFeedback}
              isVisible={showFeedback}
            />
          )}

          {interview.status === 'active' && currentQuestion && (
            <div className="answer-input-area">
              <div className="input-header" ref={inputHeaderRef}>
                <h3>{conversationMode ? '질문 입력 (대화 모드)' : '답변 입력'}</h3>
                {(conversationMode || isAnswerInputFocused || lastSaved) && (
                  <div className="input-help">
                    {conversationMode ? (
                      <>
                        <span>질문을 입력하고 AI와 대화하세요</span>
                        <button className="end-conversation-btn" onClick={endConversation}>
                          대화 종료
                        </button>
                      </>
                    ) : (
                      <>
                        {isAnswerInputFocused && (
                          <>
                            <span>Ctrl+Enter로 제출</span>
                            <span>Shift+Enter로 줄바꿈</span>
                            <span>Ctrl+S로 저장</span>
                          </>
                        )}
                        {lastSaved && (
                          <span className="save-status">
                            ✓ {lastSaved.toLocaleTimeString()}에 저장됨
                          </span>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="input-container">
                <textarea
                  ref={textareaRef}
                  value={currentAnswer}
                  onChange={(e) => {
                    console.log('[INPUT] onChange 이벤트 발생 - 새 값:', e.target.value)
                    console.log('[INPUT] 이전 currentAnswer:', currentAnswer)
                    setCurrentAnswer(e.target.value)
                    console.log('[INPUT] setCurrentAnswer 호출됨')
                  }}
                  placeholder={conversationMode ? '궁금한 점을 질문해보세요...' : '답변을 입력하세요... (구체적인 예시와 함께 설명해주세요)'}
                  className="interview-answer-textarea"
                  rows={8}
                  onFocus={() => {
                    setIsAnswerInputFocused(true)
                    if (textareaRef.current) {
                      textareaRef.current.scrollTop = 0
                    }
                  }}
                  onBlur={() => setIsAnswerInputFocused(false)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey && (e.ctrlKey || e.metaKey)) {
                      console.log('[KEY] Ctrl+Enter 키보드 단축키로 답변 제출 시도')
                      e.preventDefault()
                      e.stopPropagation()

                      if (isSubmitting) {
                        console.log('[KEY] 이미 제출 중 - 키보드 이벤트 무시')
                        return
                      }

                      submitAnswer()
                    }
                  }}
                  disabled={isSubmitting}
                />
                <div className="input-actions">
                  <div className="input-stats">
                    <span className={`char-count ${currentAnswer.length > 800 ? 'warning' : ''}`}>
                      {currentAnswer.length} / 1000
                    </span>
                    <span className="word-count">
                      {currentAnswer.split(/\s+/).filter(word => word.length > 0).length} 단어
                    </span>
                  </div>
                  <div className="action-buttons">
                    <button
                      onClick={() => setCurrentAnswer('')}
                      className="clear-btn"
                      disabled={!currentAnswer || isSubmitting}
                    >
                      <Trash2 className="v2-icon-sm interview-action-icon" />
                      지우기
                    </button>
                    <button
                      onClick={saveCurrentAnswer}
                      className="save-btn"
                      disabled={!currentAnswer || isSubmitting}
                    >
                      <Save className="v2-icon-sm interview-action-icon" />
                      저장
                    </button>
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()

                        console.log('[CLICK] submit-answer-btn 클릭됨')
                        console.log('[STATUS] 버튼 상태 체크:')
                        console.log('  - currentAnswer.trim():', Boolean(currentAnswer.trim()))
                        console.log('  - isSubmitting:', isSubmitting)
                        console.log('  - wsConnected:', wsConnected)
                        console.log('  - 버튼 disabled:', !currentAnswer.trim() || isSubmitting)

                        if (isSubmitting) {
                          console.log('[CLICK] 이미 제출 중 - 버튼 클릭 무시')
                          return
                        }

                        submitAnswer()
                      }}
                      disabled={!currentAnswer.trim() || isSubmitting}
                      className="submit-answer-btn"
                    >
                      {isSubmitting ? (
                        <>
                          <span className="interview-spinner-small"></span>
                          {conversationMode ? '질문 중...' : '제출 중...'}
                        </>
                      ) : (
                        <>
                          <Send className="v2-icon-sm interview-action-icon" />
                          {conversationMode ? '질문하기' : '답변 제출'}
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {interview.status === 'completed' && (
            <div className="interview-completed">
              <div className="completion-message">
                <h3><CheckCircle className="v2-icon-md interview-complete-icon" /> 면접이 완료되었습니다!</h3>
                <p>수고하셨습니다. 결과 리포트를 확인해보세요.</p>
                <div className="completion-actions">
                  <button
                    onClick={() => navigate('/reports')}
                    className="view-report-btn"
                  >
                    결과 보기
                  </button>
                  <button
                    onClick={() => navigate(analysisId ? `/dashboard/${analysisId}` : '/dashboard')}
                    className="back-dashboard-btn"
                  >
                    대시보드로
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </AppShellV2>

      {isFinishConfirmOpen && (
        <div
          className="modal-backdrop interview-finish-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="interview-finish-modal-title"
          onClick={(event) => {
            if (event.target === event.currentTarget && !isFinishingInterview) {
              setIsFinishConfirmOpen(false)
            }
          }}
        >
          <div className="modal modal-sm interview-finish-modal">
            <div className="modal-header">
              <h3 className="modal-title" id="interview-finish-modal-title">면접을 종료할까요?</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setIsFinishConfirmOpen(false)}
                disabled={isFinishingInterview}
                aria-label="면접 종료 확인 닫기"
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <p className="interview-finish-modal-copy">
                종료하면 현재 면접 세션이 완료 상태로 전환되고, 결과 페이지로 이동합니다.
              </p>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="clear-btn"
                onClick={() => setIsFinishConfirmOpen(false)}
                disabled={isFinishingInterview}
              >
                취소
              </button>
              <button
                type="button"
                className="submit-answer-btn interview-danger-btn"
                onClick={finishInterview}
                disabled={isFinishingInterview}
              >
                {isFinishingInterview ? '종료 중...' : '면접 종료'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
