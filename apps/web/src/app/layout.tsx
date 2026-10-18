import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { Brain, Network, GitFork, Inbox, UploadCloud, ShieldCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "OrgMind | Company Brain Knowledge Graph",
  description: "Enterprise knowledge graph platform connecting teams, documents, decisions, and chat.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans antialiased">
        {/* Global Navigation Header */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              {/* Brand Logo & Title */}
              <div className="flex items-center space-x-3">
                <Link href="/" className="flex items-center space-x-2.5">
                  <div className="bg-blue-600 text-white p-2 rounded-lg shadow-sm">
                    <Brain className="h-6 w-6" />
                  </div>
                  <div>
                    <span className="text-xl font-bold tracking-tight text-slate-900">OrgMind</span>
                    <span className="text-xs ml-2 font-mono text-slate-500 uppercase px-1.5 py-0.5 bg-slate-100 rounded border border-slate-200">
                      v0.2 Enterprise
                    </span>
                  </div>
                </Link>

                {/* Global Rule 8: Clear Synthetic Data Indicator */}
                <div className="hidden md:flex items-center ml-4 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mr-1.5"></span>
                  Synthetic Baseline: Northwind Labs (Clean Base)
                </div>
              </div>

              {/* Navigation Tabs */}
              <nav className="hidden lg:flex items-center space-x-1">
                <Link
                  href="/"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Ask Brain
                </Link>
                <Link
                  href="/graph"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Graph Explorer
                </Link>
                <Link
                  href="/decisions"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Decision Lineage
                </Link>
                <Link
                  href="/reviews"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Review Queue
                </Link>
                <Link
                  href="/ingestion"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Ingestion
                </Link>
                <Link
                  href="/audit"
                  className="px-3 py-2 text-sm font-medium text-slate-700 hover:text-blue-600 hover:bg-slate-50 rounded-md transition"
                >
                  Audit Log
                </Link>
              </nav>

              {/* Workspace Context & Active Role Indicator */}
              <div className="flex items-center space-x-3">
                <div className="text-right hidden sm:block">
                  <div className="text-xs font-semibold text-slate-900">Tenant: org_default</div>
                  <div className="text-[11px] text-slate-500">Role: Admin (Full Access)</div>
                </div>
                <div className="h-8 w-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs border border-blue-200">
                  AD
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Main Application Container */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
          OrgMind Company Brain Platform &bull; FalkorDB Knowledge Graph &bull; Grounded Citations & Bitemporal Governance
        </footer>
      </body>
    </html>
  );
}
