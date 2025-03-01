import React from 'react';
import PageHeader from './PageHeader';

const Header: React.FC = () => {
  return (
    <header className="cyberpunk-card p-4 mb-6">
      <div className="scanline"></div>
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-magenta to-primary-purple bg-clip-text text-transparent">
          Script Review
        </h1>
        <p className="text-gray-300">
          Please review and confirm the script before we start cooking!
        </p>
      </div>
    </header>
  );
};

export default Header;