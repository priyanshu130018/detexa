import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { useAuth } from '../../context/AuthContext';

export const MainLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-white text-black dark:bg-black dark:text-white transition-colors duration-150">
      <Navbar onToggleSidebar={() => setSidebarOpen((prev) => !prev)} />
      <div className="flex-1 flex overflow-hidden">
        {isAuthenticated && (
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        )}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 bg-white dark:bg-black transition-colors duration-150">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
