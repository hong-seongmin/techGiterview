import React from 'react';
import { Key } from 'lucide-react';

interface HomePageNavbarProps {
    // API Key Props
    onShowApiKeySetup: () => void;
    needsApiKeySetup: boolean;
    isConnected: boolean;
}

export const HomePageNavbar: React.FC<HomePageNavbarProps> = ({
    onShowApiKeySetup,
    needsApiKeySetup,
    isConnected,
}) => {
    const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/';

    const navLinks = [
        { label: '분석', href: '/', active: currentPath === '/' },
        { label: '내 기록', href: '/reports', active: currentPath.startsWith('/reports') },
    ];

    return (
        <nav className="navbar-container">
            <div className="navbar-content">
                {/* Logo Area */}
                <div className="navbar-logo">
                    <span className="home-v2-brand">
                        TechGiterview
                    </span>
                </div>

                <div className="navbar-nav" aria-label="주요 탐색">
                    {navLinks.map((link) => (
                        <a
                            key={link.label}
                            href={link.href}
                            className={`navbar-nav-link ${link.active ? 'navbar-nav-link--active' : ''}`}
                            aria-current={link.active ? 'page' : undefined}
                        >
                            {link.label}
                        </a>
                    ))}
                    <button
                        type="button"
                        className="navbar-nav-link navbar-nav-link--disabled"
                        title="가이드 페이지는 준비 중입니다."
                        disabled
                    >
                        가이드
                    </button>
                </div>

                {/* Right Controls */}
                <div className="navbar-controls">
                    <span
                        className={`navbar-connection-dot ${isConnected ? 'navbar-connection-dot--ok' : 'navbar-connection-dot--error'}`}
                        title={isConnected ? '백엔드 연결 정상' : '백엔드 연결 확인 필요'}
                        aria-label={isConnected ? '백엔드 연결 정상' : '백엔드 연결 확인 필요'}
                    />

                    {/* 2. API Key Settings */}
                    <button
                        onClick={onShowApiKeySetup}
                        className={`navbar-settings-btn ${needsApiKeySetup
                            ? 'navbar-settings-btn--warning'
                            : 'navbar-settings-btn--normal'
                            }`}
                        type="button"
                    >
                        <Key className={`v2-icon-sm navbar-settings-key-icon ${needsApiKeySetup ? 'navbar-settings-icon--warning' : 'navbar-settings-icon--normal'}`} />
                        <span className="navbar-settings-label">
                            {needsApiKeySetup ? 'API 설정 필요' : '설정'}
                        </span>
                    </button>
                </div>
            </div>
        </nav>
    );
};
