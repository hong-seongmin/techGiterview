import React from 'react';
import { Book, Github, Mail, MessageCircle, Zap } from 'lucide-react';
import {
  FOOTER_BRAND_DESCRIPTION,
  FOOTER_CONTACT_ITEMS,
  FOOTER_FEATURE_ITEMS,
  FOOTER_LEGAL_ITEMS,
  FOOTER_SUPPORTED_TECH_ITEMS,
} from '../../constants/footerContent';
import './SiteFooter.css';

const CONTACT_ICON_MAP = {
  email: Mail,
  repository: Github,
  issues: MessageCircle,
  docs: Book,
} as const;

const isExternalLink = (href: string): boolean =>
  href.startsWith('http://') || href.startsWith('https://');

interface SiteFooterProps {
  variant?: 'full' | 'compact';
}

interface SiteFooterContentProps {
  currentYear: number;
  repositoryLink: string;
  variant: 'full' | 'compact';
}

export const SiteFooter: React.FC<SiteFooterProps> = ({ variant = 'full' }) => {
  const currentYear = new Date().getFullYear();
  const repositoryLink =
    FOOTER_CONTACT_ITEMS.find((item) => item.key === 'repository')?.href ??
    'https://github.com/hong-seongmin/techGiterview';

  return (
    <SiteFooterContent
      currentYear={currentYear}
      repositoryLink={repositoryLink}
      variant={variant}
    />
  );
};

const SiteFooterContent: React.FC<SiteFooterContentProps> = ({
  currentYear,
  repositoryLink,
  variant,
}) => {
  if (variant === 'compact') {
    return (
      <footer className="site-footer site-footer--compact">
        <div className="site-footer__container site-footer__container--compact">
          <div className="site-footer__compact-row">
            <p className="site-footer__copyright">
              &copy; {currentYear} TechGiterview
            </p>
            <nav className="site-footer__legal-links" aria-label="빠른 링크">
              {FOOTER_LEGAL_ITEMS.map((item) => (
                <a
                  key={item.label}
                  className="site-footer__link site-footer__legal-link"
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {item.label}
                </a>
              ))}
              <a
                className="site-footer__link site-footer__legal-link"
                href={repositoryLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub
              </a>
            </nav>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="site-footer">
      <div className="site-footer__container">
        <div className="site-footer__content">
          <section className="site-footer__section site-footer__brand">
            <h3 className="site-footer__title site-footer__title--brand">
              <Zap className="site-footer__brand-icon" aria-hidden="true" />
              TechGiterview
            </h3>
            <p className="site-footer__description">{FOOTER_BRAND_DESCRIPTION}</p>
          </section>

          <section className="site-footer__section">
            <h4 className="site-footer__title">기능</h4>
            <ul className="site-footer__list">
              {FOOTER_FEATURE_ITEMS.map((item) => (
                <li key={item} className="site-footer__list-item">
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <section className="site-footer__section">
            <h4 className="site-footer__title">지원 기술</h4>
            <ul className="site-footer__list">
              {FOOTER_SUPPORTED_TECH_ITEMS.map((item) => (
                <li key={item} className="site-footer__list-item">
                  {item}
                </li>
              ))}
            </ul>
          </section>

          <section className="site-footer__section">
            <h4 className="site-footer__title">연락처</h4>
            <ul className="site-footer__list">
              {FOOTER_CONTACT_ITEMS.map((item) => {
                const Icon = CONTACT_ICON_MAP[item.key];
                const external = isExternalLink(item.href);

                return (
                  <li key={item.key} className="site-footer__list-item">
                    <a
                      className="site-footer__link site-footer__contact-link"
                      href={item.href}
                      target={external ? '_blank' : undefined}
                      rel={external ? 'noopener noreferrer' : undefined}
                    >
                      <Icon className="site-footer__contact-icon" aria-hidden="true" />
                      <span>{item.label}</span>
                    </a>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>

        <div className="site-footer__bottom">
          <p className="site-footer__copyright">
            &copy; {currentYear} TechGiterview. All rights reserved.
          </p>

          <nav className="site-footer__legal-links" aria-label="법적 링크">
            {FOOTER_LEGAL_ITEMS.map((item) => (
              <a
                key={item.label}
                className="site-footer__link site-footer__legal-link"
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
};
