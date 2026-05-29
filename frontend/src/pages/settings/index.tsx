import React, { useState, useEffect } from "react";
import Head from "next/head";
import Sidebar from "@/components/Layout/Sidebar";
import { statusApi } from "@/lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    setIsLoading(true);
    try {
      const data = await statusApi.getStatus();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load status:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Settings - My PAI</title>
      </Head>
      <Sidebar>
        <div className="p-8 overflow-y-auto h-full">
          <h1 className="text-2xl font-bold mb-8">Settings</h1>

          {/* System Status */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold mb-4">System Status</h2>
            <div className="bg-pai-card rounded-lg p-6">
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-pai-highlight"></div>
                  <span>Loading status...</span>
                </div>
              ) : status ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {Object.entries(status.agents || {}).map(
                    ([name, info]: [string, any]) => (
                      <div
                        key={name}
                        className="flex items-center gap-3 p-3 bg-pai-bg rounded-lg"
                      >
                        <div
                          className={`w-3 h-3 rounded-full ${
                            info.healthy ? "bg-green-500" : "bg-red-500"
                          }`}
                        />
                        <div>
                          <p className="font-medium capitalize">{name}</p>
                          <p className="text-xs text-pai-muted">
                            {info.healthy ? "Online" : "Offline"}
                          </p>
                        </div>
                      </div>
                    ),
                  )}
                </div>
              ) : (
                <p className="text-pai-muted">Failed to load status</p>
              )}
              <button
                onClick={loadStatus}
                className="mt-4 pai-button pai-button-secondary"
              >
                Refresh Status
              </button>
            </div>
          </section>

          {/* About */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold mb-4">About</h2>
            <div className="bg-pai-card rounded-lg p-6">
              <h3 className="text-xl font-bold text-pai-highlight mb-2">
                My PAI
              </h3>
              <p className="text-pai-muted mb-4">
                Personal AI Assistant - Your intelligent companion for
                productivity and creativity.
              </p>
              <div className="text-sm text-pai-muted space-y-1">
                <p>Version: 1.0.0</p>
                <p>
                  Built with: Next.js, FastAPI, Ollama, ChromaDB, MySQL, MinIO
                </p>
              </div>
            </div>
          </section>

          {/* Quick Links */}
          <section>
            <h2 className="text-lg font-semibold mb-4">Quick Links</h2>
            <div className="grid grid-cols-2 gap-4">
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="bg-pai-card rounded-lg p-4 hover:bg-pai-accent transition-colors"
              >
                <h3 className="font-medium">Documentation</h3>
                <p className="text-sm text-pai-muted">View the project docs</p>
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener noreferrer"
                className="bg-pai-card rounded-lg p-4 hover:bg-pai-accent transition-colors"
              >
                <h3 className="font-medium">GitHub</h3>
                <p className="text-sm text-pai-muted">View source code</p>
              </a>
            </div>
          </section>
        </div>
      </Sidebar>
    </>
  );
}
