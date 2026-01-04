'use client';

import { useAuth } from '@/contexts/auth-context';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect, ReactNode } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-muted border-t-foreground"></div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const navLinks = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/dashboard/data', label: 'Data' },
    { href: '/dashboard/recipes', label: 'Recipes' },
    { href: '/dashboard/inventory', label: 'Inventory' },
    { href: '/dashboard/forecast', label: 'Forecast' },
    { href: '/dashboard/promotions', label: 'Promotions' },
    { href: '/dashboard/settings', label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-muted/10 text-foreground">
      {/* Top navigation */}
      <header className="fixed top-0 inset-x-0 z-50 h-16 bg-stone-900 border-b border-stone-800 shadow-sm">
        <div className="h-full px-6 flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <div className="w-4 h-4 bg-stone-900 rounded-sm"></div>
              </div>
              flux
            </Link>
            <nav className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => {
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`relative px-4 py-2 text-sm font-medium transition-colors rounded-full ${isActive ? 'text-white' : 'text-stone-400 hover:text-stone-200'
                      }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="nav-pill"
                        className="absolute inset-0 bg-stone-800 rounded-full"
                        transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
                      />
                    )}
                    <span className="relative z-10">{link.label}</span>
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-stone-500 hidden sm:block">{user.email}</span>
            <button
              onClick={logout}
              className="text-sm text-stone-400 hover:text-white transition px-3 py-1.5 rounded-md hover:bg-stone-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="pt-14">
        <div className="max-w-6xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
