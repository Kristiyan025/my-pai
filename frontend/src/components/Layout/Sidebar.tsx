import React from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
  ChatBubbleLeftRightIcon,
  FolderIcon,
  Cog6ToothIcon,
  ChatBubbleLeftIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { Chat } from "@/lib/api";

interface SidebarProps {
  children: React.ReactNode;
  chats?: Chat[];
  selectedChat?: number | null;
  onSelectChat?: (chatId: number) => void;
  onNewChat?: () => void;
  onDeleteChat?: (chatId: number) => void;
}

const navItems = [
  { name: "Chat", href: "/chat", icon: ChatBubbleLeftRightIcon },
  { name: "Workspace", href: "/workspace", icon: FolderIcon },
  { name: "Settings", href: "/settings", icon: Cog6ToothIcon },
];

const formatDate = (dateString: string) => {
  if (!dateString) return "";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "";

  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString();
};

export default function Sidebar({
  children,
  chats = [],
  selectedChat,
  onSelectChat,
  onNewChat,
  onDeleteChat,
}: SidebarProps) {
  const router = useRouter();
  const isOnChatPage = router.pathname.startsWith("/chat");

  return (
    <div className="flex h-screen bg-pai-bg">
      <div className="w-64 bg-pai-card flex flex-col border-r border-pai-accent">
        <div className="p-4 border-b border-pai-accent">
          <h1 className="text-2xl font-bold text-pai-highlight">My PAI</h1>
          <p className="text-sm text-pai-muted">Personal AI Assistant</p>
        </div>

        <nav className="p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const isActive = router.pathname.startsWith(item.href);
              return (
                <li key={item.name}>
                  <Link
                    href={item.href}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive
                        ? "bg-pai-highlight text-white"
                        : "text-pai-text hover:bg-pai-accent"
                    }`}
                  >
                    <item.icon className="w-5 h-5" />
                    <span>{item.name}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {isOnChatPage && (
          <div className="flex-1 flex flex-col border-t border-pai-accent overflow-hidden">
            <div className="p-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-pai-muted">
                Conversations
              </h3>
              {onNewChat && (
                <button
                  onClick={onNewChat}
                  className="p-1.5 text-pai-muted hover:text-pai-highlight transition-colors rounded hover:bg-pai-accent"
                  title="New chat"
                >
                  <PlusIcon className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-2 pb-2">
              {chats.length === 0 ? (
                <div className="text-center py-4 text-pai-muted text-sm">
                  <ChatBubbleLeftIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No conversations</p>
                </div>
              ) : (
                <ul className="space-y-1">
                  {chats.map((chat) => (
                    <li key={chat.chat_id}>
                      <button
                        onClick={() => onSelectChat?.(chat.chat_id)}
                        className={`w-full text-left p-2 rounded-lg transition-colors group text-sm ${
                          selectedChat === chat.chat_id
                            ? "bg-pai-accent"
                            : "hover:bg-pai-accent/50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-1">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate text-sm">
                              {chat.chat_name || `Chat ${chat.chat_id}`}
                            </p>
                            <p className="text-xs text-pai-muted">
                              {formatDate(chat.updated_at)}
                            </p>
                          </div>
                          {onDeleteChat && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onDeleteChat(chat.chat_id);
                              }}
                              className="p-1 text-pai-muted hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Delete chat"
                            >
                              <TrashIcon className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <div className="p-4 border-t border-pai-accent">
          <div className="flex items-center gap-2 text-sm text-pai-muted">
            <div className="w-2 h-2 rounded-full bg-green-500"></div>
            <span>System Online</span>
          </div>
        </div>
      </div>

      <main className="flex-1 h-full min-w-0 overflow-hidden">{children}</main>
    </div>
  );
}
