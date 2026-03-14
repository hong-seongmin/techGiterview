import React, { useState, useEffect } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { apiFetch } from '../utils/apiUtils'
import { createApiHeaders, getAnalysisToken } from '../utils/apiHeaders'
import './FileContentModal.css'

interface FileContentModalProps {
  isOpen: boolean
  onClose: () => void
  filePath: string
  analysisId: string
}

interface FileContent {
  success: boolean
  file_path: string
  content: string
  size: number
  extension: string
  is_binary: boolean
  source?: string  // 'cache' 또는 'github_api'
}

export const FileContentModal: React.FC<FileContentModalProps> = ({
  isOpen,
  onClose,
  filePath,
  analysisId
}) => {
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && filePath && analysisId) {
      loadFileContent()
    }
  }, [isOpen, filePath, analysisId])

  const loadFileContent = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const analysisToken = getAnalysisToken(analysisId)
      const response = await apiFetch(
        `/api/v1/repository/analysis/${analysisId}/file-content?file_path=${encodeURIComponent(filePath)}`,
        {
          headers: createApiHeaders({
            analysisToken: analysisToken || undefined,
          }),
        }
      )
      
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('분석 접근 토큰이 없거나 만료되었습니다. 최근 분석 목록에서 다시 열어주세요.')
        }
        throw new Error('파일 내용을 불러올 수 없습니다.')
      }

      const content = await response.json()
      setFileContent(content)
    } catch (error) {
      console.error('Error loading file content:', error)
      setError(error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  const getLanguageFromExtension = (extension: string): string => {
    const languageMap: Record<string, string> = {
      'js': 'javascript',
      'jsx': 'jsx',
      'ts': 'typescript', 
      'tsx': 'tsx',
      'py': 'python',
      'java': 'java',
      'c': 'c',
      'cpp': 'cpp',
      'cc': 'cpp',
      'cxx': 'cpp',
      'h': 'c',
      'hpp': 'cpp',
      'cs': 'csharp',
      'php': 'php',
      'rb': 'ruby',
      'go': 'go',
      'rs': 'rust',
      'swift': 'swift',
      'kt': 'kotlin',
      'css': 'css',
      'scss': 'scss',
      'sass': 'sass',
      'html': 'html',
      'xml': 'xml',
      'json': 'json',
      'yaml': 'yaml',
      'yml': 'yaml',
      'toml': 'toml',
      'md': 'markdown',
      'markdown': 'markdown',
      'sql': 'sql',
      'sh': 'bash',
      'bash': 'bash',
      'zsh': 'bash',
      'fish': 'bash',
      'ps1': 'powershell',
      'dockerfile': 'dockerfile',
      'gitignore': 'gitignore',
      'gitattributes': 'gitattributes',
      'makefile': 'makefile',
      'cmake': 'cmake',
      'r': 'r',
      'R': 'r'
    }
    return languageMap[extension.toLowerCase()] || 'text'
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getFileIcon = (extension: string): string => {
    const iconMap: Record<string, string> = {
      'js': '◐',
      'jsx': '◑', 
      'ts': '◯',
      'tsx': '◉',
      'py': '◆',
      'java': '◇',
      'css': '◈',
      'html': '▣',
      'json': '▦',
      'md': '▧',
      'yml': 'YML',
      'yaml': 'YAML',
      'xml': '▤',
      'txt': '▦'
    }
    return iconMap[extension.toLowerCase()] || '◐'
  }

  if (!isOpen) return null

  return (
    <div className="file-modal-overlay" onClick={onClose}>
      <div className="file-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="file-modal-header">
          <div className="file-modal-info">
            <span className="file-modal-icon">
              {fileContent ? getFileIcon(fileContent.extension) : '◐'}
            </span>
            <div className="file-modal-title">
              <h3>{filePath}</h3>
              {fileContent && (
                <p className="file-modal-details">
                  {formatFileSize(fileContent.size)} • {fileContent.extension || 'no extension'}
                  {fileContent.source && (
                    <span className={`source-badge ${fileContent.source === 'cache' ? 'cached' : 'live'}`}>
                      {fileContent.source === 'cache' ? 'CACHED' : 'LIVE'}
                    </span>
                  )}
                </p>
              )}
            </div>
          </div>
          <button className="file-modal-close" onClick={onClose}>
            X
          </button>
        </div>

        <div className="file-modal-body">
          {isLoading ? (
            <div className="file-modal-loading">
              <div className="spinner"></div>
              <p>파일 내용을 불러오는 중... (캐시 우선 검색)</p>
            </div>
          ) : error ? (
            <div className="file-modal-error">
              <div className="error-icon">[!]</div>
              <p>{error}</p>
              <button onClick={loadFileContent} className="retry-btn">
                다시 시도
              </button>
            </div>
          ) : fileContent ? (
            fileContent.is_binary ? (
              <div className="file-modal-binary">
                <div className="binary-icon">▣</div>
                <p>이 파일은 바이너리 파일이므로 내용을 표시할 수 없습니다.</p>
              </div>
            ) : (
              <div className="file-modal-code">
                {fileContent.size > 500000 && ( // 500KB 이상인 경우 경고
                  <div className="large-file-warning">
                    <div className="warning-icon">WARNING</div>
                    <p>
                      대용량 파일입니다 ({formatFileSize(fileContent.size)}). 
                      렌더링에 시간이 걸릴 수 있습니다.
                    </p>
                  </div>
                )}
                <SyntaxHighlighter
                  language={getLanguageFromExtension(fileContent.extension)}
                  style={tomorrow}
                  showLineNumbers={true}
                  wrapLines={true}
                  customStyle={{
                    margin: 0,
                    borderRadius: '8px',
                    fontSize: '14px',
                    lineHeight: '1.5',
                    maxHeight: fileContent.size > 1000000 ? '70vh' : 'none', // 1MB 이상이면 스크롤
                    overflow: fileContent.size > 1000000 ? 'auto' : 'visible'
                  }}
                >
                  {fileContent.content}
                </SyntaxHighlighter>
              </div>
            )
          ) : null}
        </div>
      </div>
    </div>
  )
}
