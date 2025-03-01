import React from 'react';
import { Github } from 'lucide-react';

const Footer: React.FC = () => {
  return (
    <footer className="py-6 text-center text-gray-400 text-sm">
      <p className="flex items-center justify-center">
        Made with <span className="text-red-500 mx-1">❤️</span> by 
        <a 
          href="https://github.com/erniesg" 
          target="_blank" 
          rel="noopener noreferrer"
          className="mx-1 hover:text-secondary-cyan transition-colors flex items-center"
        >
          Ernie <Github size={14} className="ml-1" />
        </a> 
        & 
        <a 
          href="https://github.com/haresh-tia" 
          target="_blank" 
          rel="noopener noreferrer"
          className="mx-1 hover:text-secondary-cyan transition-colors flex items-center"
        >
          Haresh <Github size={14} className="ml-1" />
        </a>
      </p>
    </footer>
  );
};

export default Footer;