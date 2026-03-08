import { Github, Star, GitFork, X } from 'lucide-react'
import type { FileInfo, FileTreeNode, RepositoryInfo } from '../../types/dashboard'
import { FileTreeV2 } from './FileTreeV2'
import './RepositoryInfoDrawer.css'

interface RepositoryInfoDrawerProps {
  open: boolean
  onClose: () => void
  repoInfo: RepositoryInfo
  techStack: Record<string, number>
  keyFiles: FileInfo[]
  allFiles: FileTreeNode[]
  isLoadingAllFiles: boolean
  expandedFolders: Set<string>
  searchTerm: string
  onSearch: (term: string) => void
  onToggleFolder: (path: string) => void
  onFileClick: (node: FileTreeNode) => void
  onLoadAllFiles: () => void
}

export function RepositoryInfoDrawer({
  open,
  onClose,
  repoInfo,
  techStack,
  keyFiles,
  allFiles,
  isLoadingAllFiles,
  expandedFolders,
  searchTerm,
  onSearch,
  onToggleFolder,
  onFileClick,
  onLoadAllFiles,
}: RepositoryInfoDrawerProps) {
  const topTech = Object.entries(techStack || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return (
    <>
      <div
        className={`dashboard-drawer-backdrop ${open ? 'dashboard-drawer-backdrop--open' : ''}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside className={`dashboard-repo-drawer ${open ? 'dashboard-repo-drawer--open' : ''}`} aria-hidden={!open}>
        <div className="dashboard-repo-drawer-header">
          <div className="dashboard-repo-drawer-title">
            <Github className="v2-icon-sm" />
            <div>
              <h2>{repoInfo.owner}/{repoInfo.name}</h2>
              <p>저장소 정보와 파일 탐색</p>
            </div>
          </div>
          <button className="v2-btn v2-btn-ghost v2-btn-sm" onClick={onClose} aria-label="저장소 정보 닫기">
            <X className="v2-btn-icon" />
          </button>
        </div>

        <div className="dashboard-repo-drawer-body">
          {repoInfo.description ? (
            <p className="dashboard-repo-drawer-description">{repoInfo.description}</p>
          ) : null}

          <div className="dashboard-repo-drawer-stats">
            <span><Star className="v2-icon-xs" />{repoInfo.stars.toLocaleString()}</span>
            <span><GitFork className="v2-icon-xs" />{repoInfo.forks.toLocaleString()}</span>
            {repoInfo.language ? <span>{repoInfo.language}</span> : null}
          </div>

          <section className="dashboard-repo-drawer-section">
            <span className="dashboard-repo-drawer-label">기술 스택</span>
            <div className="dashboard-repo-drawer-chip-grid">
              {topTech.length > 0 ? (
                topTech.map(([tech, score]) => (
                  <span key={tech} className="v2-badge v2-badge-arch">
                    {tech} {(score * 100).toFixed(0)}%
                  </span>
                ))
              ) : (
                <span className="dashboard-repo-drawer-empty">아직 기술 스택 정보가 없습니다.</span>
              )}
            </div>
          </section>

          <section className="dashboard-repo-drawer-section">
            <span className="dashboard-repo-drawer-label">주요 파일</span>
            <ul className="dashboard-repo-drawer-file-list">
              {keyFiles.slice(0, 12).map((file) => (
                <li key={file.path}>{file.path}</li>
              ))}
            </ul>
          </section>

          <section className="dashboard-repo-drawer-section">
            <div className="dashboard-repo-drawer-section-head">
              <span className="dashboard-repo-drawer-label">전체 파일 탐색</span>
              <button className="v2-btn v2-btn-outline v2-btn-sm" onClick={onLoadAllFiles}>
                {allFiles.length > 0 ? '새로고침' : '불러오기'}
              </button>
            </div>

            {(allFiles.length > 0 || isLoadingAllFiles) ? (
              <div className="dashboard-repo-drawer-tree">
                <FileTreeV2
                  nodes={allFiles}
                  expandedFolders={expandedFolders}
                  onToggleFolder={onToggleFolder}
                  onFileClick={onFileClick}
                  searchTerm={searchTerm}
                  onSearch={onSearch}
                  isLoading={isLoadingAllFiles}
                />
              </div>
            ) : (
              <p className="dashboard-repo-drawer-empty">
                필요할 때만 전체 파일을 불러옵니다.
              </p>
            )}
          </section>
        </div>
      </aside>
    </>
  )
}
