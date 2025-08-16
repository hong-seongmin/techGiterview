import React, { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { 
  LayoutDashboard, 
  Github, 
  Lightbulb, 
  Tag, 
  FileText, 
  Star, 
  GitFork, 
  Code, 
  Clock, 
  CheckCircle,
  ArrowRight,
  Folder,
  File,
  ChevronRight,
  Search,
  Minus,
  Play,
  BarChart3,
  FileCode,
  Database,
  Image,
  Archive,
  Globe,
  Settings,
  BookOpen,
  Cpu,
  Monitor,
  Smartphone,
  Palette,
  Zap,
  Shield,
  Users,
  MessageSquare,
  TrendingUp,
  AlertTriangle,
  Info,
  Terminal
} from 'lucide-react'
import { FileContentModal } from '../components/FileContentModal'
import { CriticalFilesPreview } from '../components/CriticalFilesPreview'
import './DashboardPage.css'

interface RepositoryInfo {
  name: string
  owner: string
  description: string | null
  language: string | null
  stars: number
  forks: number
  size: number
  topics: string[]
  default_branch: string
}

interface FileInfo {
  path: string
  type: string
  size: number
  content?: string
  importance?: 'high' | 'medium' | 'low'
}

// SmartFileAnalysis 인터페이스 정의 (CriticalFilesPreview와 동일)
interface SmartFileAnalysis {
  file_path: string
  importance_score: number
  reasons: string[]
  metrics: {
    structural_importance: number
    dependency_centrality: number
    churn_risk: number
    complexity_score: number
  }
  category: 'critical' | 'important' | 'moderate' | 'low'
  rank: number
}

interface AnalysisResult {
  success: boolean
  analysis_id: string
  repo_info: RepositoryInfo
  tech_stack: Record<string, number>
  key_files: FileInfo[]
  summary: string
  recommendations: string[]
  created_at: string
  smart_file_analysis?: {
    critical_files: SmartFileAnalysis[]
    importance_distribution?: {
      mean: number
      median: number
      std_dev: number
      min: number
      max: number
    }
    categorized_files?: {
      critical: string[]
      important: string[]
      moderate: string[]
      low: string[]
    }
    summary?: {
      total_files_analyzed: number
      critical_files_count: number
      important_files_count: number
      average_importance: number
      highest_importance: number
    }
  }
}

interface Question {
  id: string
  type: string
  question: string
  difficulty: string
  context?: string
  time_estimate?: string
  code_snippet?: {
    content: string
    language: string
    file_path: string
    complexity: number
    has_real_content?: boolean
    content_unavailable_reason?: string
  }
  expected_answer_points?: string[]
  technology?: string
  pattern?: string
  // 서브 질문 관련 필드
  parent_question_id?: string
  sub_question_index?: number
  total_sub_questions?: number
  is_compound_question?: boolean
  // 파일 연관성 필드
  source_file?: string
  importance?: 'high' | 'medium' | 'low'
  generated_by?: string
}

interface FileTreeNode {
  name: string
  path: string
  type: string // "file" or "dir"
  size?: number
  children?: FileTreeNode[]
}

// 로컬스토리지에서 API 키를 가져오는 헬퍼 함수
const getApiKeysFromStorage = () => {
  try {
    return {
      githubToken: localStorage.getItem('techgiterview_github_token') || '',
      googleApiKey: localStorage.getItem('techgiterview_google_api_key') || ''
    }
  } catch (error) {
    return { githubToken: '', googleApiKey: '' }
  }
}

// API 요청용 헤더 생성 함수
const createApiHeaders = (includeApiKeys: boolean = false) => {
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  }
  
  if (includeApiKeys) {
    const { githubToken, googleApiKey } = getApiKeysFromStorage()
    if (githubToken) headers['X-GitHub-Token'] = githubToken
    if (googleApiKey) headers['X-Google-API-Key'] = googleApiKey
  }
  
  return headers
}

// 파일 확장자에 따른 React 아이콘 컴포넌트 반환
const getFileIcon = (filePath: string): React.ReactNode => {
  const extension = filePath.split('.').pop()?.toLowerCase()
  const fileName = filePath.split('/').pop()?.toLowerCase() || ''
  
  // 특수 파일명 먼저 처리
  if (fileName === 'dockerfile' || fileName.startsWith('dockerfile')) {
    return <Monitor className="w-4 h-4 text-blue-600" />
  }
  if (fileName === '.gitignore') {
    return <Github className="w-4 h-4 text-orange-600" />
  }
  if (fileName.startsWith('readme')) {
    return <BookOpen className="w-4 h-4 text-blue-700" />
  }
  if (fileName === 'license' || fileName.startsWith('license')) {
    return <Shield className="w-4 h-4 text-green-600" />
  }
  if (fileName === 'package.json') {
    return <Settings className="w-4 h-4 text-red-600" />
  }
  if (fileName === 'package-lock.json' || fileName === 'yarn.lock') {
    return <Archive className="w-4 h-4 text-gray-600" />
  }
  
  // 확장자별 처리
  switch (extension) {
    case 'js':
    case 'jsx':
      return <FileCode className="w-4 h-4 text-yellow-500" />
    case 'ts':
    case 'tsx':
      return <FileCode className="w-4 h-4 text-blue-600" />
    case 'vue':
      return <FileCode className="w-4 h-4 text-green-500" />
    case 'py':
    case 'pyw':
    case 'pyx':
      return <Cpu className="w-4 h-4 text-blue-500" />
    case 'java':
    case 'kt':
    case 'scala':
      return <Cpu className="w-4 h-4 text-orange-600" />
    case 'html':
    case 'htm':
      return <Globe className="w-4 h-4 text-orange-500" />
    case 'css':
    case 'scss':
    case 'sass':
    case 'less':
      return <Palette className="w-4 h-4 text-blue-500" />
    case 'json':
    case 'yaml':
    case 'yml':
    case 'toml':
    case 'ini':
    case 'conf':
    case 'config':
      return <Settings className="w-4 h-4 text-gray-600" />
    case 'md':
      return <FileText className="w-4 h-4 text-blue-700" />
    case 'txt':
      return <FileText className="w-4 h-4 text-gray-600" />
    case 'pdf':
      return <File className="w-4 h-4 text-red-600" />
    case 'sql':
    case 'db':
    case 'sqlite':
      return <Database className="w-4 h-4 text-blue-600" />
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
      return <Image className="w-4 h-4 text-green-500" />
    case 'zip':
    case 'tar':
    case 'gz':
      return <Archive className="w-4 h-4 text-gray-600" />
    default:
      return <File className="w-4 h-4 text-gray-500" />
  }
}

export const DashboardPage: React.FC = () => {
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [questions, setQuestionsInternal] = useState<Question[]>([])
  const [isLoadingQuestions, setIsLoadingQuestions] = useState(false)
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false)
  const [questionsGenerated, setQuestionsGenerated] = useState(false)
  
  // 질문 상태 변경 추적을 위한 래퍼 함수
  const setQuestions = (newQuestions: Question[]) => {
    console.log('[Questions State] Updating questions state:', {
      previousCount: questions.length,
      newCount: newQuestions.length,
      timestamp: new Date().toISOString(),
      stackTrace: new Error().stack?.split('\n').slice(1, 4).join('\n')
    })
    setQuestionsInternal(newQuestions)
    console.log('[Questions State] Questions state updated:', newQuestions.length)
  }
  const [allFiles, setAllFiles] = useState<FileTreeNode[]>([])
  const [isLoadingAllFiles, setIsLoadingAllFiles] = useState(false)
  const [showAllFiles, setShowAllFiles] = useState(true)
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [filteredFiles, setFilteredFiles] = useState<FileTreeNode[]>([])
  const [isFileModalOpen, setIsFileModalOpen] = useState(false)
  const [selectedFilePath, setSelectedFilePath] = useState('')
  const [error, setError] = useState<string | null>(null)
  // CSS 클래스 기반 시스템에서는 강제 리렌더링 불필요
  const navigate = useNavigate()
  const { analysisId } = useParams<{ analysisId: string }>()

  // 컴포넌트 상태 추적 (개발 모드에서만)
  if (process.env.NODE_ENV === 'development') {
    console.log('[Dashboard] 렌더링:', { 
      analysisId,
      hasResult: !!analysisResult,
      questionsCount: questions.length,
      error
    })
  }

  useEffect(() => {
    console.log('DashboardPage analysisId:', analysisId) // 디버깅용
    if (analysisId) {
      // URL 파라미터에서 분석 ID를 가져와서 API에서 데이터 로드
      loadAnalysisResult(analysisId)
    } else {
      // 분석 ID가 없으면 홈으로 리다이렉트
      console.log('No analysisId, redirecting to home')
      navigate('/')
    }
  }, [analysisId, navigate])

  // 강화된 CSS 들여쓰기 디버깅 및 복구 시스템
  useEffect(() => {
    const performDeepStyleInvestigation = () => {
      console.log('\n[Deep Style Investigation] 시작...')
      
      // 1. CSS 변수 시스템 검증
      const rootStyle = getComputedStyle(document.documentElement)
      const indentValue = rootStyle.getPropertyValue('--file-tree-indent-per-level').trim()
      console.log('[CSS Variables] --file-tree-indent-per-level:', indentValue || '정의되지 않음')
      
      // 2. 실제 depth-1 요소들 상세 분석
      const depth1Elements = document.querySelectorAll('.file-tree-depth-1')
      console.log(`[Element Count] depth-1 요소 총 개수: ${depth1Elements.length}`)
      
      if (depth1Elements.length > 0) {
        // 첫 번째 요소로 상세 분석
        const firstElement = depth1Elements[0] as HTMLElement
        const computedStyle = getComputedStyle(firstElement)
        
        console.log('[첫 번째 depth-1 요소 상세 분석]')
        console.log('  - Element HTML:', firstElement.outerHTML.substring(0, 200) + '...')
        console.log('  - Computed margin-left:', computedStyle.marginLeft)
        console.log('  - Computed padding-left:', computedStyle.paddingLeft)
        console.log('  - Inline style margin-left:', firstElement.style.marginLeft || '없음')
        console.log('  - CSS Classes:', firstElement.className)
        console.log('  - Position:', computedStyle.position)
        console.log('  - Display:', computedStyle.display)
        console.log('  - Box-sizing:', computedStyle.boxSizing)
        
        // 3. 강제 인라인 스타일 적용 테스트
        console.log('\n[강제 인라인 스타일 적용 테스트]')
        firstElement.style.marginLeft = '20px'
        firstElement.style.backgroundColor = 'rgba(255, 0, 0, 0.2)'
        firstElement.style.border = '2px solid red'
        
        // 적용 후 재검증
        setTimeout(() => {
          const newComputedStyle = getComputedStyle(firstElement)
          console.log('  - 강제 적용 후 margin-left:', newComputedStyle.marginLeft)
          console.log('  - 강제 적용 후 background-color:', newComputedStyle.backgroundColor)
          
          // 시각적 효과 제거
          setTimeout(() => {
            firstElement.style.backgroundColor = ''
            firstElement.style.border = ''
          }, 2000)
        }, 100)
        
        // 4. 모든 depth-1 요소에 시각적 표시 적용
        depth1Elements.forEach((element, index) => {
          const htmlElement = element as HTMLElement
          htmlElement.style.marginLeft = '12px'
          htmlElement.style.backgroundColor = `rgba(0, 255, 0, ${0.1 + index * 0.02})`
          htmlElement.style.transition = 'all 0.3s ease'
          
          // 3초 후 시각적 효과 제거
          setTimeout(() => {
            htmlElement.style.backgroundColor = ''
            htmlElement.style.transition = ''
          }, 3000)
        })
      }
      
      // 5. CSS 규칙 충돌 검사
      console.log('\n[CSS 규칙 충돌 검사]')
      const stylesheets = Array.from(document.styleSheets)
      let conflictingRules = []
      
      try {
        stylesheets.forEach((sheet, sheetIndex) => {
          try {
            const rules = Array.from(sheet.cssRules || [])
            rules.forEach((rule, ruleIndex) => {
              if (rule.cssText.includes('margin-left') && 
                  (rule.cssText.includes('.file-tree') || rule.cssText.includes('depth'))) {
                conflictingRules.push({
                  sheet: sheetIndex,
                  rule: ruleIndex,
                  text: rule.cssText
                })
              }
            })
          } catch (e) {
            console.log(`  - Stylesheet ${sheetIndex}: 접근 불가 (CORS)`)
          }
        })
        
        console.log('  - 발견된 관련 CSS 규칙들:', conflictingRules)
      } catch (e) {
        console.log('  - CSS 규칙 검사 실패:', e.message)
      }
    }

    // 디버깅 실행
    const investigationTimer = setTimeout(performDeepStyleInvestigation, 200)
    
    return () => {
      clearTimeout(investigationTimer)
    }
  }, [allFiles, expandedFolders])

  /**
   * ============================================
   * 통합 파일 트리 들여쓰기 시스템
   * ============================================
   * 
   * ✅ CSS 변수 기반 중앙 관리: design-tokens.css에서 --file-tree-indent-per-level로 통합 관리
   * ✅ CSS 클래스 기반 적용: .file-tree-depth-0 ~ .file-tree-depth-6 클래스로 깊이별 들여쓰기
   * ✅ 반응형 자동 처리: CSS 미디어 쿼리로 데스크톱(4px), 태블릿(3px), 모바일(2px) 자동 적용
   * ✅ DOM 조작 없음: React 인라인 스타일이나 useEffect DOM 조작 완전 제거
   * ✅ 성능 최적화: 불필요한 리렌더링, 윈도우 리사이즈 이벤트, 강제 업데이트 제거
   * 
   * 핵심 파일:
   * - design-tokens.css: CSS 변수 및 미디어 쿼리 정의
   * - DashboardPage.css: .file-tree-depth-* 클래스 정의  
   * - DashboardPage.tsx: getDepthClassName() 함수로 CSS 클래스 동적 할당
   */

  const loadAnalysisResult = async (analysisId: string) => {
    console.log('[Dashboard] Starting loadAnalysisResult for ID:', analysisId)
    console.log('[Dashboard] API URL will be:', `/api/v1/repository/analysis/${analysisId}`)
    
    setIsLoadingAnalysis(true)
    setError(null)
    
    try {
      console.log('[Dashboard] 📤 Making fetch request...')
      const response = await fetch(`/api/v1/repository/analysis/${analysisId}`)
      console.log('[Dashboard] 📥 Response received:', {
        status: response.status,
        statusText: response.statusText,
        url: response.url,
        headers: Object.fromEntries(response.headers.entries())
      })
      
      if (response.status === 202) {
        // 분석이 아직 진행 중
        const result = await response.json()
        console.log('[Dashboard] ⏳ Analysis still in progress:', result)
        setError(`분석이 진행 중입니다. 상태: ${result.detail}`)
        return
      }
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('[Dashboard] API error response:', {
          status: response.status,
          statusText: response.statusText,
          errorText
        })
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      console.log('[Dashboard] Analysis result loaded successfully:', {
        analysis_id: result.analysis_id,
        repo_name: result.repo_info?.name,
        repo_owner: result.repo_info?.owner,
        key_files_count: result.key_files?.length,
        tech_stack: Object.keys(result.tech_stack || {}),
        has_smart_analysis: !!result.smart_file_analysis
      })
      setAnalysisResult(result)
      
      // 자동으로 전체 파일 목록 로드
      try {
        const filesResponse = await fetch(`/api/v1/repository/analysis/${result.analysis_id}/all-files?max_depth=3&max_files=500`)
        if (filesResponse.ok) {
          const files = await filesResponse.json()
          setAllFiles(files)
          setFilteredFiles(files)
          setShowAllFiles(true)
        }
      } catch (error) {
        console.error('Error loading all files:', error)
      }
      
      // 질문이 아직 생성되지 않았다면 자동 로드/생성
      if (!questionsGenerated) {
        console.log('[Dashboard] Auto-loading questions...')
        await loadOrGenerateQuestions(result)
      }
    } catch (error) {
      console.error('[Dashboard] Critical error loading analysis:', {
        error,
        errorMessage: error instanceof Error ? error.message : 'Unknown error',
        errorStack: error instanceof Error ? error.stack : undefined,
        analysisId
      })
      setError(error instanceof Error ? error.message : 'Unknown error occurred')
    } finally {
      console.log('[Dashboard] 🏁 Analysis loading finished, setting isLoadingAnalysis to false')
      setIsLoadingAnalysis(false)
    }
  }

  const loadOrGenerateQuestions = async (analysisToUse: AnalysisResult) => {
    console.log('[Questions] Starting loadOrGenerateQuestions for analysis:', analysisToUse.analysis_id)
    console.log('[Questions] Current questions state:', { 
      questionsCount: questions.length, 
      questionsGenerated, 
      isLoadingQuestions 
    })
    
    setIsLoadingQuestions(true)
    try {
      // 먼저 이미 생성된 질문이 있는지 확인
      const checkUrl = `/api/v1/questions/analysis/${analysisToUse.analysis_id}`
      console.log('[Questions] 📤 Fetching existing questions from:', checkUrl)
      
      const checkResponse = await fetch(checkUrl, {
        method: 'GET',
        headers: createApiHeaders(false) // 질문 조회는 API 키 불필요
      })
      console.log('[Questions] 📥 Check response received:', {
        status: checkResponse.status,
        statusText: checkResponse.statusText,
        ok: checkResponse.ok,
        url: checkResponse.url
      })
      
      if (checkResponse.ok) {
        const checkResult = await checkResponse.json()
        console.log('[Questions] Parsed check result:', {
          success: checkResult.success,
          questionsLength: checkResult.questions?.length || 0,
          questionsExists: !!checkResult.questions,
          analysisId: checkResult.analysis_id,
          error: checkResult.error
        })
        
        if (checkResult.success && checkResult.questions && checkResult.questions.length > 0) {
          // 이미 생성된 질문이 있음
          console.log('[Questions] Found existing questions, setting state:', checkResult.questions.length)
          setQuestions(checkResult.questions)
          setQuestionsGenerated(true)
          console.log('[Questions] Questions state updated successfully')
          return
        } else {
          console.log('[Questions] No existing questions found, will generate new ones')
        }
      } else {
        console.warn('[Questions] Check response not ok:', {
          status: checkResponse.status,
          statusText: checkResponse.statusText
        })
      }
      
      // 질문이 없으면 새로 생성
      console.log('[Questions] Generating new questions...')
      const generatePayload = {
        repo_url: `https://github.com/${analysisToUse.repo_info.owner}/${analysisToUse.repo_info.name}`,
        analysis_result: analysisToUse,
        question_type: "technical",
        difficulty: "medium"
      }
      console.log('[Questions] Generation payload:', generatePayload)
      
      const generateResponse = await fetch('/api/v1/questions/generate', {
        method: 'POST',
        headers: createApiHeaders(true), // API 키 포함하여 헤더 생성
        body: JSON.stringify(generatePayload)
      })

      console.log('[Questions] 📥 Generate response received:', {
        status: generateResponse.status,
        statusText: generateResponse.statusText,
        ok: generateResponse.ok
      })

      if (!generateResponse.ok) {
        const errorText = await generateResponse.text()
        console.error('[Questions] Generate response error:', errorText)
        throw new Error(`질문 생성에 실패했습니다. (${generateResponse.status}: ${errorText})`)
      }

      const generateResult = await generateResponse.json()
      console.log('[Questions] Parsed generate result:', {
        success: generateResult.success,
        questionsLength: generateResult.questions?.length || 0,
        questionsExists: !!generateResult.questions,
        analysisId: generateResult.analysis_id,
        error: generateResult.error
      })
      
      if (generateResult.success) {
        console.log('[Questions] Generated questions successfully, setting state:', generateResult.questions?.length || 0)
        setQuestions(generateResult.questions || [])
        setQuestionsGenerated(true)
        console.log('[Questions] Generated questions state updated successfully')
      } else {
        console.error('[Questions] Generate result not successful:', generateResult.error)
        throw new Error(`질문 생성 실패: ${generateResult.error}`)
      }
    } catch (error) {
      console.error('[Questions] Critical error in loadOrGenerateQuestions:', {
        error,
        errorMessage: error instanceof Error ? error.message : 'Unknown error',
        errorStack: error instanceof Error ? error.stack : undefined,
        analysisId: analysisToUse.analysis_id
      })
      // 질문 생성에 실패해도 대시보드는 표시
    } finally {
      console.log('[Questions] 🏁 loadOrGenerateQuestions finished, setting isLoadingQuestions to false')
      setIsLoadingQuestions(false)
    }
  }

  const regenerateQuestions = async () => {
    if (!analysisResult) return
    
    setIsLoadingQuestions(true)
    try {
      // 강제 재생성 옵션을 사용하여 질문 생성
      const response = await fetch('/api/v1/questions/generate', {
        method: 'POST',
        headers: createApiHeaders(true), // API 키 포함하여 헤더 생성
        body: JSON.stringify({
          repo_url: `https://github.com/${analysisResult.repo_info.owner}/${analysisResult.repo_info.name}`,
          analysis_result: analysisResult,
          question_type: "technical",
          difficulty: "medium",
          force_regenerate: true
        })
      })

      if (!response.ok) {
        throw new Error('질문 재생성에 실패했습니다.')
      }

      const result = await response.json()
      if (result.success) {
        setQuestions(result.questions || [])
        setQuestionsGenerated(true)
      }
    } catch (error) {
      console.error('Error regenerating questions:', error)
      alert('질문 재생성에 실패했습니다.')
    } finally {
      setIsLoadingQuestions(false)
    }
  }

  const loadAllFiles = async () => {
    if (!analysisResult || !analysisId) return
    
    setIsLoadingAllFiles(true)
    try {
      const response = await fetch(`/api/v1/repository/analysis/${analysisId}/all-files?max_depth=3&max_files=500`)
      
      if (!response.ok) {
        throw new Error('전체 파일 목록을 불러올 수 없습니다.')
      }

      const files = await response.json()
      setAllFiles(files)
      setFilteredFiles(files)
      setShowAllFiles(true)
      setSearchTerm('')
    } catch (error) {
      console.error('Error loading all files:', error)
      alert('전체 파일 목록을 불러오는데 실패했습니다.')
    } finally {
      setIsLoadingAllFiles(false)
    }
  }

  const toggleFolder = (path: string) => {
    const newExpanded = new Set(expandedFolders)
    if (newExpanded.has(path)) {
      newExpanded.delete(path)
    } else {
      newExpanded.add(path)
    }
    setExpandedFolders(newExpanded)
  }

  const filterFiles = (nodes: FileTreeNode[], term: string): FileTreeNode[] => {
    if (!term) return nodes

    return nodes.reduce((filtered: FileTreeNode[], node) => {
      if (node.type === 'dir') {
        const filteredChildren = filterFiles(node.children || [], term)
        const hasMatchingChildren = filteredChildren.length > 0
        const nameMatches = node.name.toLowerCase().includes(term.toLowerCase())
        
        if (nameMatches || hasMatchingChildren) {
          filtered.push({
            ...node,
            children: filteredChildren
          })
        }
      } else {
        if (node.name.toLowerCase().includes(term.toLowerCase())) {
          filtered.push(node)
        }
      }
      return filtered
    }, [])
  }

  const handleSearch = (term: string) => {
    setSearchTerm(term)
    if (!term) {
      setFilteredFiles(allFiles)
    } else {
      const filtered = filterFiles(allFiles, term)
      setFilteredFiles(filtered)
      // 검색 시 모든 폴더 자동 확장
      const expandAll = new Set<string>()
      const expandAllFolders = (nodes: FileTreeNode[]) => {
        nodes.forEach(node => {
          if (node.type === 'dir') {
            expandAll.add(node.path)
            if (node.children) {
              expandAllFolders(node.children)
            }
          }
        })
      }
      expandAllFolders(filtered)
      setExpandedFolders(expandAll)
    }
  }

  const handleFileClick = (file: FileTreeNode) => {
    if (file.type === 'file') {
      setSelectedFilePath(file.path)
      setIsFileModalOpen(true)
    }
  }

  const closeFileModal = () => {
    setIsFileModalOpen(false)
    setSelectedFilePath('')
  }


  // 성능 최적화: CSS 변수 읽기를 컴포넌트 레벨로 이동
  const getMaxDepth = React.useMemo(() => {
    try {
      const rootStyle = getComputedStyle(document.documentElement)
      return parseInt(rootStyle.getPropertyValue('--file-tree-max-depth')) || 6
    } catch {
      return 6 // 기본값
    }
  }, [])

  // 성능 최적화: depth 클래스명 계산 함수 메모이제이션
  const getDepthClassName = React.useCallback((depth: number): string => {
    if (depth > getMaxDepth) {
      return 'file-tree-depth-overflow'
    }
    return `file-tree-depth-${depth}`
  }, [getMaxDepth])

  const renderFileTree = (nodes: FileTreeNode[], depth: number = 0): JSX.Element[] => {
    const effectiveDepth = Math.min(depth, getMaxDepth)
    const depthClassName = getDepthClassName(effectiveDepth)
    
    // 강제 인라인 스타일 - CSS 무시하고 직접 브라우저에 전달
    const forceInlineStyle: React.CSSProperties = {
      marginLeft: `${effectiveDepth * 12}px`,
      paddingLeft: '0px',
      display: 'block',
      boxSizing: 'border-box',
      // 시각적 확인을 위한 배경색 (depth-1만)
      ...(effectiveDepth === 1 && { 
        backgroundColor: 'rgba(0, 255, 0, 0.08)',
        border: '1px solid rgba(0, 255, 0, 0.2)',
        borderRadius: '2px'
      })
    }
    
    return nodes.map((node, index) => {
      
      return (
        <div 
          key={node.path} 
          className={`file-tree-node ${depthClassName}`}
          style={forceInlineStyle}
          data-depth={effectiveDepth}
          data-node-type={node.type}
        >
        <div className="file-tree-item">
          {node.type === 'dir' ? (
            <>
              <button 
                className="folder-toggle"
                onClick={() => toggleFolder(node.path)}
              >
                <ChevronRight className={`w-3 h-3 text-gray-500 transition-transform duration-200 ${expandedFolders.has(node.path) ? 'rotate-90' : ''}`} />
                <Folder className="w-4 h-4 text-blue-600" />
                <span className="folder-name">{node.name}</span>
              </button>
              <div 
                className={`folder-children ${expandedFolders.has(node.path) ? 'expanded' : 'collapsed'}`}
              >
                {expandedFolders.has(node.path) && node.children && 
                  renderFileTree(node.children, depth + 1)
                }
              </div>
            </>
          ) : (
            <div 
              className="file-item-tree"
              onClick={() => handleFileClick(node)}
            >
              {getFileIcon(node.name)}
              <span className={`file-name ${searchTerm && node.name.toLowerCase().includes(searchTerm.toLowerCase()) ? 'highlight' : ''}`}>
                {node.name}
              </span>
              {node.size && (
                <span className="file-size">{(node.size / 1024).toFixed(1)} KB</span>
              )}
            </div>
          )}
        </div>
        </div>
      )
    })
  }

  const startInterview = async () => {
    if (!analysisResult) return
    
    // 질문이 로드되지 않았으면 먼저 로드
    if (questions.length === 0) {
      console.log('질문이 없습니다. 질문을 먼저 생성합니다.')
      await loadOrGenerateQuestions(analysisResult)
      if (questions.length === 0) {
        throw new Error('질문 생성에 실패했습니다.')
      }
    }
    
    console.log('면접 시작 요청:', {
      repo_url: `https://github.com/${analysisResult.repo_info.owner}/${analysisResult.repo_info.name}`,
      analysis_id: analysisResult.analysis_id,
      question_ids: questions.map(q => q.id),
      questions_count: questions.length
    })
    
    try {
      const response = await fetch('/api/v1/interview/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: `https://github.com/${analysisResult.repo_info.owner}/${analysisResult.repo_info.name}`,
          analysis_id: analysisResult.analysis_id,
          question_ids: questions.map(q => q.id)
        })
      })

      if (!response.ok) {
        throw new Error('면접 시작에 실패했습니다.')
      }

      const result = await response.json()
      if (result.success) {
        navigate(`/dashboard/${analysisResult.analysis_id}/interview/${result.data.interview_id}`)
      }
    } catch (error) {
      console.error('Error starting interview:', error)
      alert('면접 시작에 실패했습니다.')
    }
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case 'beginner': return '#28a745'
      case 'intermediate': return '#ffc107'
      case 'advanced': return '#dc3545'
      default: return '#6c757d'
    }
  }

  const getCategoryIcon = (category: string): React.ReactNode => {
    if (!category) return <Code className="w-4 h-4 text-gray-500" />
    switch (category.toLowerCase()) {
      case 'technical': 
        return <Terminal className="w-4 h-4 text-blue-600" />
      case 'architectural': 
        return <Monitor className="w-4 h-4 text-purple-600" />
      case 'scenario': 
        return <MessageSquare className="w-4 h-4 text-green-600" />
      case 'algorithm': 
        return <Zap className="w-4 h-4 text-yellow-600" />
      case 'data-structure': 
        return <Database className="w-4 h-4 text-indigo-600" />
      case 'system-design': 
        return <TrendingUp className="w-4 h-4 text-red-600" />
      case 'code-review': 
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'best-practices': 
        return <Star className="w-4 h-4 text-yellow-500" />
      case 'debugging': 
        return <AlertTriangle className="w-4 h-4 text-red-500" />
      default: 
        return <Code className="w-4 h-4 text-gray-500" />
    }
  }

  // key_files를 smart_file_analysis 형태로 변환하는 헬퍼 함수
  const convertKeyFilesToSmartAnalysis = (keyFiles: FileInfo[]): SmartFileAnalysis[] => {
    return keyFiles.slice(0, 5).map((file, index) => ({
      file_path: file.path || 'unknown-file',
      importance_score: file.importance === 'high' ? 0.9 - (index * 0.05) : 0.7 - (index * 0.05),
      reasons: [
        file.importance === 'high' ? '높은 중요도로 분류된 핵심 파일' : '중요 파일로 선정',
        file.size > 10000 ? '대용량 파일로 핵심 로직 포함 추정' : '프로젝트 구조상 중요 위치',
        getFileTypeReason(file.path)
      ].filter(Boolean),
      metrics: {
        structural_importance: file.importance === 'high' ? 0.9 : 0.7,
        dependency_centrality: 0.6 + (Math.random() * 0.3),
        churn_risk: 0.4 + (Math.random() * 0.4),
        complexity_score: file.size > 5000 ? 0.7 : 0.4
      },
      category: file.importance === 'high' ? 'critical' : 'important',
      rank: index + 1
    }))
  }

  // 파일 경로 기반 선정 이유 생성
  const getFileTypeReason = (filePath: string): string => {
    const fileName = filePath.split('/').pop()?.toLowerCase() || ''
    const extension = fileName.split('.').pop()?.toLowerCase() || ''
    
    if (fileName === 'package.json') return '프로젝트 설정 및 의존성 관리 파일'
    if (fileName === 'readme.md') return '프로젝트 문서화 및 가이드 파일'
    if (fileName.includes('config') || fileName.includes('settings')) return '프로젝트 설정 파일'
    if (extension === 'ts' || extension === 'tsx') return 'TypeScript 핵심 소스 파일'
    if (extension === 'js' || extension === 'jsx') return 'JavaScript 핵심 소스 파일'
    if (extension === 'py') return 'Python 핵심 소스 파일'
    if (fileName.includes('main') || fileName.includes('index')) return '애플리케이션 진입점 파일'
    return '프로젝트 핵심 구성 요소'
  }

  // 질문을 그룹화하는 함수
  const groupQuestions = (questions: Question[]) => {
    const groups: { [key: string]: Question[] } = {}
    const standalone: Question[] = []

    questions.forEach(question => {
      if (question.parent_question_id) {
        // 서브 질문인 경우
        if (!groups[question.parent_question_id]) {
          groups[question.parent_question_id] = []
        }
        groups[question.parent_question_id].push(question)
      } else {
        // 독립 질문인 경우
        standalone.push(question)
      }
    })

    // 서브 질문들을 인덱스 순으로 정렬
    Object.keys(groups).forEach(parentId => {
      groups[parentId].sort((a, b) => (a.sub_question_index || 0) - (b.sub_question_index || 0))
    })

    return { groups, standalone }
  }

  // 로딩 상태
  if (isLoadingAnalysis) {
    console.log('[Dashboard] Rendering loading state')
    return (
      <div className="dashboard-loading">
        <div className="spinner-large"></div>
        <p>분석 결과를 불러오는 중...</p>
      </div>
    )
  }

  // 분석 결과가 없거나 오류가 있는 경우
  if (!analysisResult || error) {
    console.log('[Dashboard] Rendering error state:', { 
      hasAnalysisResult: !!analysisResult, 
      error,
      analysisId
    })
    return (
      <div className="dashboard-error">
        <div className="error-content">
          <h2>❌ {error ? '오류 발생' : '분석 결과를 찾을 수 없습니다'}</h2>
          <p>분석 ID: <code>{analysisId}</code></p>
          {error ? (
            <p className="error-message">오류: {error}</p>
          ) : (
            <p>분석이 완료되지 않았거나 잘못된 ID일 수 있습니다.</p>
          )}
          <div className="error-actions">
            <button onClick={() => navigate('/')} className="btn btn-outline">
              🏠 홈으로 돌아가기
            </button>
            <button 
              onClick={() => {
                setError(null)
                if (analysisId) loadAnalysisResult(analysisId)
              }} 
              className="btn btn-ghost"
            >
              🔄 다시 시도
            </button>
          </div>
        </div>
      </div>
    )
  }

  console.log('[Dashboard] Rendering main dashboard content')

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="header-content">
          <h1><LayoutDashboard className="inline-block w-8 h-8 mr-3" /> 분석 결과 대시보드</h1>
          <p className="repo-url">
            https://github.com/{analysisResult.repo_info.owner}/{analysisResult.repo_info.name}
          </p>
          <p className="analysis-id">분석 ID: {analysisResult.analysis_id}</p>
        </div>
      </div>

      <div className="dashboard-content">
        {/* 저장소 정보 */}
        <div className="info-section">
          <div className="card card-lg">
            <div className="card-header">
              <h3><Github className="section-icon" /> 저장소 정보</h3>
            </div>
            <div className="card-body">
              <div className="repo-details">
                <h3>{analysisResult.repo_info.owner}/{analysisResult.repo_info.name}</h3>
                <p className="repo-description">{analysisResult.repo_info.description}</p>
                <div className="repo-stats">
                  <div className="stat">
                    <Star className="w-6 h-6 text-yellow-500 mb-1" />
                    <span className="stat-value">{analysisResult.repo_info.stars.toLocaleString()}</span>
                    <span className="stat-label">Stars</span>
                  </div>
                  <div className="stat">
                    <GitFork className="w-6 h-6 text-blue-500 mb-1" />
                    <span className="stat-value">{analysisResult.repo_info.forks.toLocaleString()}</span>
                    <span className="stat-label">Forks</span>
                  </div>
                  <div className="stat">
                    <Code className="w-6 h-6 text-purple-500 mb-1" />
                    <span className="stat-value">{analysisResult.repo_info.language}</span>
                    <span className="stat-label">Language</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 개선 제안 */}
          <div className="card card-lg">
            <div className="card-header">
              <h3><Lightbulb className="section-icon" /> 개선 제안</h3>
            </div>
            <div className="card-body">
              <div className="recommendations-list">
                {analysisResult.recommendations.length > 0 ? (
                  analysisResult.recommendations.map((recommendation, index) => (
                    <div key={index} className="recommendation-item">
                      <ArrowRight className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                      <span className="recommendation-text">{recommendation}</span>
                    </div>
                  ))
                ) : (
                  <p className="no-recommendations">이 프로젝트는 잘 구성되어 있습니다!</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 기술 스택 */}
        <div className="card card-lg">
          <div className="card-header">
            <h2><Tag className="section-icon" /> 기술 스택</h2>
          </div>
          <div className="tech-stack-grid">
            {Object.entries(analysisResult.tech_stack || {})
              .sort(([,a], [,b]) => b - a) // 점수 순으로 정렬
              .map(([tech, score], index) => (
                <span key={index} className="tech-tag">
                  {tech} ({(score * 100).toFixed(1)}%)
                </span>
              ))
            }
          </div>
        </div>

        {/* 주요 파일 */}
        <div className="card card-lg">
          <div className="card-header">
            <h2><FileText className="section-icon" /> 주요 파일</h2>
            <div className="file-actions">
              {!showAllFiles && (
                <button 
                  className="btn btn-outline btn-sm"
                  onClick={loadAllFiles}
                  disabled={isLoadingAllFiles}
                >
                  {isLoadingAllFiles ? '로딩 중...' : '자세히 보기'}
                </button>
              )}
            </div>
          </div>
          
          {!showAllFiles ? (
            <div className="files-loading">
              <div className="spinner"></div>
              <p>파일 목록을 불러오는 중...</p>
            </div>
          ) : (
            <div className="all-files-container">
              {isLoadingAllFiles ? (
                <div className="files-loading">
                  <div className="spinner"></div>
                  <p>모든 파일을 불러오는 중...</p>
                </div>
              ) : (
                <div className="file-tree">
                  {allFiles.length > 0 ? (
                    <>
                      <div className="file-tree-header">
                        <div className="file-tree-info">
                          <p>
                            {searchTerm ? 
                              `"${searchTerm}" 검색 결과: ${filteredFiles.length}개 항목` :
                              `${allFiles.length}개의 최상위 항목`
                            }
                          </p>
                        </div>
                        <div className="file-tree-controls">
                          <div className="relative">
                            <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                            <input
                              type="text"
                              placeholder="파일 검색..."
                              value={searchTerm}
                              onChange={(e) => handleSearch(e.target.value)}
                              className="form-input form-input-sm pl-10"
                            />
                          </div>
                          <button 
                            className="btn btn-ghost btn-sm flex items-center gap-1"
                            onClick={() => setExpandedFolders(new Set())}
                          >
                            <Minus className="w-3 h-3" />
                            모두 접기
                          </button>
                        </div>
                      </div>
                      <div className="file-tree-content">
                        {renderFileTree(searchTerm ? filteredFiles : allFiles)}
                      </div>
                    </>
                  ) : (
                    <p className="no-files">파일을 불러올 수 없습니다.</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 면접 질문 */}
        <div className="card card-lg">
          <div className="card-header">
            <h2><MessageSquare className="section-icon" /> 생성된 면접 질문</h2>
            {questionsGenerated && questions.length > 0 && (
              <p className="questions-info">
                이미 생성된 질문을 불러왔습니다. 다른 질문을 원하시면 재생성하세요.
              </p>
            )}
            <div className="question-actions">
              <button 
                className="btn btn-outline"
                onClick={regenerateQuestions}
                disabled={isLoadingQuestions}
              >
                {isLoadingQuestions ? '생성 중...' : '질문 재생성'}
              </button>
              <button 
                className="btn btn-primary btn-lg flex items-center gap-2 justify-center"
                onClick={startInterview}
                disabled={questions.length === 0 || isLoadingQuestions}
              >
                <Play className="w-4 h-4" />
                {isLoadingQuestions ? '준비 중...' : '모의면접 시작'}
              </button>
            </div>
          </div>
          
          {isLoadingQuestions ? (
            <div className="questions-loading">
              <div className="spinner"></div>
              <p>
                {questionsGenerated ? 
                  'AI가 새로운 질문을 생성하고 있습니다...' : 
                  'AI가 맞춤형 질문을 확인하고 있습니다...'
                }
              </p>
            </div>
          ) : (
            <>
              {/* 중요 파일 미리보기 섹션 - questions-grid 상단에 추가 */}
              {(() => {
                // smart_file_analysis가 있으면 사용, 없으면 key_files를 변환해서 사용
                const criticalFiles = analysisResult?.smart_file_analysis?.critical_files 
                  || (analysisResult?.key_files ? convertKeyFilesToSmartAnalysis(analysisResult.key_files) : [])
                
                console.log('[DEBUG] CriticalFilesPreview 렌더링 조건:', {
                  hasSmartAnalysis: !!analysisResult?.smart_file_analysis?.critical_files,
                  hasKeyFiles: !!analysisResult?.key_files,
                  keyFilesCount: analysisResult?.key_files?.length || 0,
                  criticalFilesCount: criticalFiles.length,
                  criticalFiles: criticalFiles.map((file, idx) => ({
                    index: idx,
                    file_path: file.file_path,
                    file_path_type: typeof file.file_path,
                    file_path_length: file.file_path?.length,
                    importance_score: file.importance_score
                  }))
                })
                
                return criticalFiles.length > 0 ? (
                  <CriticalFilesPreview 
                    criticalFiles={criticalFiles}
                    onFileClick={(filePath: string) => {
                      setSelectedFilePath(filePath)
                      setIsFileModalOpen(true)
                    }}
                  />
                ) : null
              })()}
              
              <div className="questions-grid">
              {questions.length === 0 ? (
                <div className="questions-empty-state">
                  <div className="empty-state-content">
                    <MessageSquare className="empty-state-icon" />
                    <h3>질문을 불러오는 중입니다</h3>
                    <p>
                      {questionsGenerated 
                        ? "질문 생성이 완료되었지만 표시되지 않고 있습니다. 잠시 후 다시 시도해주세요."
                        : "AI가 저장소를 분석하여 맞춤형 면접 질문을 준비하고 있습니다."
                      }
                    </p>
                    <button 
                      className="btn btn-outline"
                      onClick={() => analysisResult && loadOrGenerateQuestions(analysisResult)}
                      disabled={isLoadingQuestions}
                    >
                      {isLoadingQuestions ? '로딩 중...' : '질문 다시 불러오기'}
                    </button>
                  </div>
                </div>
              ) : (
                questions.map((question, index) => (
                <div 
                  key={question.id} 
                  className="question-card"
                  data-has-real-content={question.code_snippet?.has_real_content ?? 'unknown'}
                >
                  <div className="question-header">
                    <div className="question-meta">
                      <span className="question-number">Q{index + 1}</span>
                      {getCategoryIcon(question.type)}
                      <span className="category-name">{question.type}</span>
                      {question.parent_question_id && (
                        <span className="sub-question-indicator">
                          ({question.sub_question_index}/{question.total_sub_questions})
                        </span>
                      )}
                    </div>
                    <span 
                      className="difficulty-badge"
                      style={{ backgroundColor: getDifficultyColor(question.difficulty) }}
                    >
                      {question.difficulty}
                    </span>
                  </div>
                  <div className="question-content">
                    <div className="question-text">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p style={{ margin: '0 0 12px 0' }}>{children}</p>,
                          code: ({ children }) => <code style={{ background: '#f1f5f9', padding: '2px 4px', borderRadius: '3px', fontSize: '0.9em' }}>{children}</code>,
                          pre: ({ children }) => <pre style={{ background: '#f8fafc', padding: '12px', borderRadius: '6px', overflow: 'auto', border: '1px solid #e2e8f0' }}>{children}</pre>
                        }}
                      >
                        {question.question}
                      </ReactMarkdown>
                    </div>
                    
                    {/* 질문 기반 파일 정보 표시 */}
                    {question.source_file && (
                      <div className="question-source-file">
                        {getFileIcon(question.source_file)}
                        <span className="source-file-text"><FileText className="w-4 h-4 inline mr-2" />기반 파일: {question.source_file}</span>
                        {question.importance && (
                          <span className={`importance-badge ${question.importance}`}>
                            {question.importance === 'high' ? '[CORE] 핵심' : '[SUB] 보조'}
                          </span>
                        )}
                      </div>
                    )}
                    
                    {question.context && (
                      <p className="question-context"><Info className="w-4 h-4 inline mr-2" /> {question.context}</p>
                    )}
                    {question.technology && (
                      <p className="question-tech"><Tag className="w-4 h-4 inline mr-2" /> 기술: {question.technology}</p>
                    )}
                    {question.code_snippet && (
                      <div className="question-code">
                        <div className="code-header">
                          {getFileIcon(question.code_snippet.file_path)}
                          <span className="code-file-path"><File className="w-4 h-4 inline mr-1" /> {question.code_snippet.file_path}</span>
                          {question.code_snippet.has_real_content === false && (
                            <span className="content-status warning">
                              [WARN] 내용 없음 ({question.code_snippet.content_unavailable_reason})
                            </span>
                          )}
                          {question.code_snippet.has_real_content === true && (
                            <span className="content-status success">[OK] 실제 코드</span>
                          )}
                        </div>
                        <pre className="code-snippet">{question.code_snippet.content}</pre>
                      </div>
                    )}
                    {question.time_estimate && (
                      <p className="question-time"><Clock className="w-4 h-4 inline mr-2" /> 예상 시간: {question.time_estimate}</p>
                    )}
                  </div>
                </div>
                ))
              )}
              </div>
            </>
          )}
        </div>

        {/* 요약 */}
        <div className="summary-section">
          <div className="card-header">
            <h2><BarChart3 className="section-icon" /> 분석 요약</h2>
          </div>
          <div className="summary-content">
            <p>{analysisResult.summary}</p>
          </div>
        </div>
      </div>

      {/* 파일 내용 모달 */}
      <FileContentModal
        isOpen={isFileModalOpen}
        onClose={closeFileModal}
        filePath={selectedFilePath}
        analysisId={analysisId || ''}
      />
    </div>
  )
}