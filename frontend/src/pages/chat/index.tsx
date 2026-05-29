import React, { useState, useEffect, useRef } from "react";
import Head from "next/head";
import Sidebar from "@/components/Layout/Sidebar";
import ChatMessage from "@/components/Chat/ChatMessage";
import ChatInput from "@/components/Chat/ChatInput";
import { chatApi, workspaceApi, Message, Chat } from "@/lib/api";

const UPLOAD_DIRECTORY = "/uploaded_documents";

export default function ChatPage() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChat, setSelectedChat] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chats on mount
  useEffect(() => {
    loadChats();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadChats = async () => {
    try {
      const chatList = await chatApi.getChats();
      setChats(chatList);
    } catch (err) {
      console.error("Failed to load chats:", err);
    }
  };

  const loadMessages = async (chatId: number) => {
    try {
      const chatMessages = await chatApi.getMessages(chatId);
      setMessages(
        chatMessages.map((m) => ({
          role: m.user_role as "user" | "assistant",
          content: m.message_text,
        })),
      );
    } catch (err) {
      console.error("Failed to load messages:", err);
    }
  };

  const handleSelectChat = async (chatId: number) => {
    setSelectedChat(chatId);
    await loadMessages(chatId);
  };

  const handleNewChat = async () => {
    try {
      const newChat = await chatApi.createChat(`Chat ${Date.now()}`);
      setChats([newChat, ...chats]);
      setSelectedChat(newChat.chat_id);
      setMessages([]);
    } catch (err) {
      console.error("Failed to create chat:", err);
    }
  };

  const handleDeleteChat = async (chatId: number) => {
    if (!confirm("Are you sure you want to delete this conversation?")) return;

    try {
      await chatApi.deleteChat(chatId);
      setChats(chats.filter((c) => c.chat_id !== chatId));
      if (selectedChat === chatId) {
        setSelectedChat(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  const handleSendMessage = async (content: string, files?: File[]) => {
    if (!content.trim() && (!files || files.length === 0)) return;

    // Upload files first if any
    let uploadedFilePaths: string[] = [];
    let uploadErrors: string[] = [];

    if (files && files.length > 0) {
      setIsLoading(true);
      setError(null);

      try {
        // Ensure upload directory exists
        try {
          await workspaceApi.createDirectory(UPLOAD_DIRECTORY);
        } catch (e) {
          // Directory might already exist, that's fine
        }

        // Upload each file
        for (const file of files) {
          const filePath = `${UPLOAD_DIRECTORY}/${file.name}`;
          try {
            await workspaceApi.uploadFile(filePath, file);
            uploadedFilePaths.push(filePath);
          } catch (uploadErr: any) {
            // Check for 409 Conflict (file already exists)
            if (uploadErr.response?.status === 409) {
              // Try with timestamp suffix
              const timestamp = Date.now();
              const nameParts = file.name.split(".");
              const ext = nameParts.length > 1 ? `.${nameParts.pop()}` : "";
              const baseName = nameParts.join(".");
              const newFilePath = `${UPLOAD_DIRECTORY}/${baseName}_${timestamp}${ext}`;

              try {
                await workspaceApi.uploadFile(newFilePath, file);
                uploadedFilePaths.push(newFilePath);
              } catch (retryErr: any) {
                uploadErrors.push(
                  `${file.name}: ${retryErr.response?.data?.detail || retryErr.message}`,
                );
              }
            } else {
              uploadErrors.push(
                `${file.name}: ${uploadErr.response?.data?.detail || uploadErr.message}`,
              );
            }
          }
        }
      } catch (err: any) {
        console.error("Failed to upload files:", err);
        setError(`Failed to upload files: ${err.message}`);
        setIsLoading(false);
        return;
      }

      // If all uploads failed, show error and abort
      if (uploadedFilePaths.length === 0 && uploadErrors.length > 0) {
        setError(`Upload failed:\n${uploadErrors.join("\n")}`);
        setIsLoading(false);
        return;
      }

      // If some uploads failed, show warning but continue
      if (uploadErrors.length > 0) {
        setError(`Some files failed to upload:\n${uploadErrors.join("\n")}`);
      }
    }

    // Build message with file context
    let finalMessage = content;
    if (uploadedFilePaths.length > 0) {
      const fileList = uploadedFilePaths.map((p) => `- ${p}`).join("\n");
      finalMessage = content
        ? `${content}\n\n[Attached files uploaded to workspace:\n${fileList}]`
        : `[Attached files uploaded to workspace:\n${fileList}]`;
    }

    // Add user message to UI immediately
    const userMessage: Message = { role: "user", content: finalMessage };
    setMessages([...messages, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await chatApi.sendMessage(
        finalMessage,
        selectedChat || undefined,
        messages,
      );

      // Update chat ID if new - wait a moment for DB to sync
      if (response.chat_id && response.chat_id !== selectedChat) {
        setSelectedChat(response.chat_id);
        // Small delay to ensure chat is saved before loading list
        await new Promise((resolve) => setTimeout(resolve, 300));
        await loadChats();
      }

      // Add assistant response
      const assistantMessage: Message = {
        role: "assistant",
        content: response.response,
        images: response.images,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error("Failed to send message:", err);
      setError(err.message || "Failed to get response");
      // Add error message
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, I encountered an error: ${err.message || "Unknown error"}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Chat - My PAI</title>
      </Head>
      <Sidebar
        chats={chats}
        selectedChat={selectedChat}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
      >
        <div className="flex h-full overflow-hidden">
          {/* Chat area */}
          <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-pai-muted">
                  <div className="text-6xl mb-4">👋</div>
                  <h2 className="text-2xl font-bold text-pai-text mb-2">
                    Welcome to My PAI
                  </h2>
                  <p className="text-center max-w-md">
                    I'm your Personal AI Assistant. Ask me anything, upload
                    files, or let me help you with tasks!
                  </p>
                  <div className="mt-8 grid grid-cols-2 gap-4 max-w-lg">
                    {[
                      "Search my documents for...",
                      "Play some music",
                      "Convert this file to PDF",
                      "Calculate 2^10 - 512",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => handleSendMessage(suggestion)}
                        className="p-3 bg-pai-card rounded-lg text-sm text-left hover:bg-pai-accent transition-colors"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((message, index) => (
                    <ChatMessage key={index} message={message} />
                  ))}
                  {isLoading && (
                    <div className="chat-message assistant">
                      <div className="flex items-center gap-2">
                        <div className="animate-pulse flex gap-1">
                          <div className="w-2 h-2 bg-pai-highlight rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-pai-highlight rounded-full animate-bounce delay-100"></div>
                          <div className="w-2 h-2 bg-pai-highlight rounded-full animate-bounce delay-200"></div>
                        </div>
                        <span className="text-pai-muted text-sm">
                          PAI is thinking...
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* Error banner */}
            {error && (
              <div className="mx-4 mb-2 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300 text-sm flex items-start justify-between">
                <div className="whitespace-pre-wrap">{error}</div>
                <button
                  onClick={() => setError(null)}
                  className="ml-3 text-red-400 hover:text-red-200 font-bold"
                >
                  ×
                </button>
              </div>
            )}

            {/* Input */}
            <ChatInput
              onSend={handleSendMessage}
              disabled={isLoading}
              placeholder={
                isLoading ? "Waiting for response..." : "Type your message..."
              }
            />
          </div>
        </div>
      </Sidebar>
    </>
  );
}
