import React from 'react';
import { useAppStore } from './store';
import Header from './components/Header';
import GlobalSettings from './components/GlobalSettings';
import BottomNavigation from './components/BottomNavigation';
import LandingPage from './components/LandingPage';
import ProcessingPage from './components/ProcessingPage';
import CompletionPage from './components/CompletionPage';
import PageHeader from './components/PageHeader';
import Footer from './components/Footer';

function App() {
  const { currentPage } = useAppStore();

  // Render different pages based on the current page state
  if (currentPage === 'landing') {
    return <LandingPage />;
  }

  if (currentPage === 'processing') {
    return <ProcessingPage />;
  }

  if (currentPage === 'completion') {
    return <CompletionPage />;
  }

  // Script review page (default)
  return (
    <div className="min-h-screen bg-gradient-to-br from-background-dark to-background-darker flex flex-col">
      <div className="cyber-grid"></div>
      <div className="container mx-auto px-4 py-8 max-w-6xl flex-grow">
        <PageHeader 
          subtitle="Please review and confirm the script before we start cooking!"
        />
        <GlobalSettings />
        <BottomNavigation />
      </div>
      <Footer />
    </div>
  );
}

export default App;