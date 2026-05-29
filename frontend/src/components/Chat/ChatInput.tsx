import React, { useState, useRef, useEffect, KeyboardEvent } from "react";
import {
  PaperAirplaneIcon,
  MicrophoneIcon,
  PaperClipIcon,
  StopIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onend: (() => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

interface AttachedFile {
  file: File;
  name: string;
}

interface ChatInputProps {
  onSend: (message: string, files?: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Type your message...",
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    const SpeechRecognitionAPI =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognitionAPI) {
      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = event.results[0][0].transcript;
        setMessage((prev) => (prev ? prev + " " + transcript : transcript));
      };

      recognition.onerror = () => {
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  const handleVoiceInput = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in your browser");
      return;
    }

    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  };

  const handleSend = () => {
    if ((message.trim() || attachedFiles.length > 0) && !disabled) {
      onSend(
        message.trim(),
        attachedFiles.length > 0 ? attachedFiles.map((f) => f.file) : undefined,
      );
      setMessage("");
      setAttachedFiles([]);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const newFiles: AttachedFile[] = Array.from(files).map((file) => ({
        file,
        name: file.name,
      }));
      setAttachedFiles((prev) => [...prev, ...newFiles]);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="border-t border-pai-accent p-4 bg-pai-card">
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {attachedFiles.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-2 bg-pai-accent rounded-lg px-3 py-1.5 text-sm"
            >
              <PaperClipIcon className="w-4 h-4 text-pai-muted" />
              <span className="text-pai-text truncate max-w-[150px]">
                {file.name}
              </span>
              <button
                type="button"
                onClick={() => handleRemoveFile(index)}
                className="text-pai-muted hover:text-pai-error transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-3">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="hidden"
          multiple
        />

        <button
          type="button"
          onClick={handleAttachClick}
          className="p-2 text-pai-muted hover:text-pai-text transition-colors"
          title="Attach file"
          disabled={disabled}
        >
          <PaperClipIcon className="w-5 h-5" />
        </button>

        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="pai-input resize-none pr-12"
            style={{ maxHeight: "200px" }}
          />
        </div>

        <button
          type="button"
          onClick={handleVoiceInput}
          className={`p-2 transition-colors ${
            isRecording
              ? "text-red-500 animate-pulse"
              : "text-pai-muted hover:text-pai-text"
          }`}
          title={isRecording ? "Stop recording" : "Voice input"}
          disabled={disabled}
        >
          <MicrophoneIcon className="w-5 h-5" />
        </button>

        {disabled ? (
          <button
            type="button"
            className="pai-button pai-button-secondary flex items-center gap-2"
            title="Stop generating"
          >
            <StopIcon className="w-5 h-5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!message.trim() && attachedFiles.length === 0}
            className="pai-button pai-button-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Send message"
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      <p className="text-xs text-pai-muted mt-2 text-center">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  );
}
