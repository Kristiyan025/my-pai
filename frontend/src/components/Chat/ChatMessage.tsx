import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { Message, MessageImage } from "@/lib/api";
import {
  UserCircleIcon,
  CpuChipIcon,
  ClipboardIcon,
  CheckIcon,
  SpeakerWaveIcon,
  StopIcon,
  ArrowDownTrayIcon,
} from "@heroicons/react/24/outline";

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [copiedMessage, setCopiedMessage] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isUser = message.role === "user";

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const copyMessageToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessage(true);
      setTimeout(() => setCopiedMessage(false), 2000);
    } catch (err) {
      console.error("Failed to copy message:", err);
    }
  };

  const readAloud = async () => {
    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
      return;
    }

    if (isPlaying && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      return;
    }

    setIsLoading(true);

    if (window.speechSynthesis) {
      const utterance = new SpeechSynthesisUtterance(message.content);
      utterance.onend = () => {
        setIsPlaying(false);
      };
      utterance.onerror = () => {
        console.error("Browser TTS error");
        setIsPlaying(false);
      };

      window.speechSynthesis.speak(utterance);
      setIsPlaying(true);
      setIsLoading(false);
    } else {
      console.error("Speech synthesis not supported");
      setIsLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return (
    <div className={`chat-message ${isUser ? "user" : "assistant"}`}>
      <div className="flex items-start gap-3">
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
            isUser ? "bg-pai-highlight" : "bg-pai-accent"
          }`}
        >
          {isUser ? (
            <UserCircleIcon className="w-5 h-5" />
          ) : (
            <CpuChipIcon className="w-5 h-5" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">
              {isUser ? "You" : "PAI"}
            </span>
          </div>

          <div className="prose prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || "");
                  const codeString = String(children).replace(/\n$/, "");

                  if (!inline && match) {
                    return (
                      <div className="relative group">
                        <button
                          onClick={() => copyToClipboard(codeString)}
                          className="absolute top-2 right-2 p-1 rounded bg-pai-accent opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          {copied ? (
                            <CheckIcon className="w-4 h-4 text-green-500" />
                          ) : (
                            <ClipboardIcon className="w-4 h-4" />
                          )}
                        </button>
                        <SyntaxHighlighter
                          style={vscDarkPlus}
                          language={match[1]}
                          PreTag="div"
                          {...props}
                        >
                          {codeString}
                        </SyntaxHighlighter>
                      </div>
                    );
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {message.images && message.images.length > 0 && (
            <div className="mt-3 space-y-3">
              {message.images.map((img, idx) => (
                <div key={idx} className="relative group">
                  {img.title && (
                    <p className="text-sm text-pai-muted mb-1">{img.title}</p>
                  )}
                  {img.base64 ? (
                    <img
                      src={`data:${img.content_type || "image/jpeg"};base64,${img.base64}`}
                      alt={img.title || `Image ${idx + 1}`}
                      className="max-w-full max-h-96 rounded-lg border border-pai-accent"
                    />
                  ) : img.url ? (
                    <img
                      src={img.url}
                      alt={img.title || `Image ${idx + 1}`}
                      className="max-w-full max-h-96 rounded-lg border border-pai-accent"
                    />
                  ) : img.path ? (
                    <div className="text-sm text-pai-muted">
                      Image saved to:{" "}
                      <code className="bg-pai-accent px-1 rounded">
                        {img.path}
                      </code>
                    </div>
                  ) : null}
                  {img.source_url && (
                    <a
                      href={img.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-pai-highlight hover:underline mt-1 block"
                    >
                      View source
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2 mt-2">
            <button
              onClick={copyMessageToClipboard}
              className="p-1.5 rounded hover:bg-pai-accent transition-colors text-gray-400 hover:text-white"
              title="Copy message"
            >
              {copiedMessage ? (
                <CheckIcon className="w-4 h-4 text-green-500" />
              ) : (
                <ClipboardIcon className="w-4 h-4" />
              )}
            </button>
            <button
              onClick={readAloud}
              disabled={isLoading}
              className="p-1.5 rounded hover:bg-pai-accent transition-colors text-gray-400 hover:text-white disabled:opacity-50"
              title={isPlaying ? "Stop" : "Read aloud"}
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              ) : isPlaying ? (
                <StopIcon className="w-4 h-4 text-red-400" />
              ) : (
                <SpeakerWaveIcon className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
