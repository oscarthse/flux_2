'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/auth-context';

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.push('/dashboard');
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-amber-50">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-200 border-t-amber-900"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-amber-50">
      {/* Navigation */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-amber-50/90 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-semibold text-stone-900 tracking-tight">
            flux
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/login" className="text-sm text-stone-600 hover:text-stone-900 transition">
              Sign in
            </Link>
            <Link
              href="/register"
              className="text-sm px-4 py-2 bg-stone-900 text-white rounded-full hover:bg-stone-800 transition"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-sm font-medium text-amber-700 mb-4">For restaurant owners who want to run smarter</p>
          <h1 className="text-4xl md:text-6xl font-semibold text-stone-900 leading-tight tracking-tight mb-6">
            Know what your kitchen needs before it needs it
          </h1>
          <p className="text-lg text-stone-600 max-w-2xl mx-auto mb-10 leading-relaxed">
            Flux helps independent restaurants reduce food waste and save money by predicting what you will sell,
            tracking what you have, and telling you exactly what to order.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/register"
              className="px-6 py-3 bg-stone-900 text-white rounded-full hover:bg-stone-800 transition text-sm font-medium"
            >
              Start your free trial
            </Link>
            <Link
              href="#how-it-works"
              className="px-6 py-3 text-stone-700 hover:text-stone-900 transition text-sm font-medium"
            >
              See how it works
            </Link>
          </div>
        </div>
      </section>

      {/* Social proof */}
      <section className="py-10 border-y border-amber-200 bg-amber-100/50">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <p className="text-sm text-stone-600">
            Built for restaurants in Barcelona. Designed for chefs, not accountants.
          </p>
        </div>
      </section>

      {/* Problem/Solution */}
      <section className="py-24 px-6 bg-white" id="how-it-works">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-semibold text-stone-900 mb-4">Stop guessing, start knowing</h2>
            <p className="text-stone-600 max-w-2xl mx-auto">
              Most restaurants lose 5-10% of revenue to food waste and stockouts.
              Flux gives you visibility into what is actually happening in your kitchen.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <div className="bg-amber-50 rounded-2xl p-8">
              <div className="w-10 h-10 bg-amber-200 rounded-xl flex items-center justify-center mb-5 text-amber-800 font-semibold">
                1
              </div>
              <h3 className="text-lg font-medium text-stone-900 mb-2">Upload your sales data</h3>
              <p className="text-stone-600 text-sm leading-relaxed">
                Connect your point of sale or upload a simple spreadsheet. We handle the rest.
              </p>
            </div>

            <div className="bg-amber-50 rounded-2xl p-8">
              <div className="w-10 h-10 bg-amber-200 rounded-xl flex items-center justify-center mb-5 text-amber-800 font-semibold">
                2
              </div>
              <h3 className="text-lg font-medium text-stone-900 mb-2">See what is coming</h3>
              <p className="text-stone-600 text-sm leading-relaxed">
                Get a daily forecast of what you will likely sell based on your history, the weather, and local events.
              </p>
            </div>

            <div className="bg-amber-50 rounded-2xl p-8">
              <div className="w-10 h-10 bg-amber-200 rounded-xl flex items-center justify-center mb-5 text-amber-800 font-semibold">
                3
              </div>
              <h3 className="text-lg font-medium text-stone-900 mb-2">Order with confidence</h3>
              <p className="text-stone-600 text-sm leading-relaxed">
                Know exactly how much of each ingredient to buy. No more guessing, no more waste.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-24 px-6 bg-stone-900">
        <div className="max-w-5xl mx-auto">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl font-semibold text-white mb-6">
                Built for the way restaurants actually work
              </h2>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="w-5 h-5 rounded-full bg-amber-500 flex-shrink-0 mt-0.5"></div>
                  <div>
                    <p className="font-medium text-white">No complicated setup</p>
                    <p className="text-sm text-stone-400">Upload a CSV and you are running in minutes.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-5 h-5 rounded-full bg-amber-500 flex-shrink-0 mt-0.5"></div>
                  <div>
                    <p className="font-medium text-white">Works with your recipes</p>
                    <p className="text-sm text-stone-400">Add your dishes and we calculate ingredient needs automatically.</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-5 h-5 rounded-full bg-amber-500 flex-shrink-0 mt-0.5"></div>
                  <div>
                    <p className="font-medium text-white">Speaks your language</p>
                    <p className="text-sm text-stone-400">No jargon, no dashboards that need a PhD to understand.</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="bg-stone-800 rounded-2xl p-10 text-center">
              <p className="text-5xl font-semibold text-amber-400 mb-2">15-25%</p>
              <p className="text-stone-400">reduction in food waste for typical users</p>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonial */}
      <section className="py-24 px-6 bg-amber-100">
        <div className="max-w-3xl mx-auto text-center">
          <blockquote className="text-2xl font-medium text-stone-900 leading-relaxed mb-6">
            "We cut our food waste by 22% in the first month. The ordering recommendations alone save us hours every week."
          </blockquote>
          <p className="text-stone-600">Marc Rodriguez, La Boqueria Bites</p>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-semibold text-stone-900 mb-4">
            Ready to stop throwing money away?
          </h2>
          <p className="text-stone-600 mb-8">
            Start with a 14-day free trial. No credit card required.
          </p>
          <Link
            href="/register"
            className="inline-block px-8 py-4 bg-stone-900 text-white rounded-full hover:bg-stone-800 transition font-medium"
          >
            Get started for free
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 bg-amber-50 border-t border-amber-200">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-stone-500">2024 Flux. Made in Barcelona.</p>
          <div className="flex gap-6 text-sm text-stone-500">
            <a href="#" className="hover:text-stone-900 transition">Privacy</a>
            <a href="#" className="hover:text-stone-900 transition">Terms</a>
            <a href="mailto:hello@flux.restaurant" className="hover:text-stone-900 transition">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
