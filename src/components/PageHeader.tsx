import React from 'react';
import { motion } from 'framer-motion';

interface PageHeaderProps {
  title?: string;
  subtitle?: string | null;
}

const PageHeader: React.FC<PageHeaderProps> = ({ 
  title, 
  subtitle = "Text to TikTok in 3 easy steps: Type, Review, Publish!"
}) => {
  return (
    <div className="text-center mb-12">
      <h1 className="text-5xl md:text-7xl font-orbitron mb-4">
        万象更新
      </h1>
      <div className="glitch-container">
        <h2 className="text-3xl md:text-4xl font-orbitron text-secondary-cyan mb-4">
          <span className="glitch-text" data-text="Everything Has Changed">Everything Has Changed</span>
        </h2>
      </div>
      {title && (
        <h3 className="text-2xl md:text-3xl font-orbitron mt-8 text-white">
          {title}
        </h3>
      )}
      {subtitle && (
        <p className="mt-6 text-xl text-gray-300 max-w-2xl mx-auto">
          {subtitle}
        </p>
      )}
    </div>
  );
};

export default PageHeader;