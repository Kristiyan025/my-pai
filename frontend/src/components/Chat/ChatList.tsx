import React from "react";
import { Chat } from "@/lib/api";
import {
  ChatBubbleLeftIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";

interface ChatListProps {
  chats: Chat[];
  selectedChat: number | null;
  onSelect: (chatId: number) => void;
  onNew: () => void;
  onDelete?: (chatId: number) => void;
}

export default function ChatList({
  chats,
  selectedChat,
  onSelect,
  onNew,
  onDelete,
}: ChatListProps) {
  const formatDate = (dateString: string) => {
    if (!dateString) return "";

    const date = new Date(dateString);

    if (isNaN(date.getTime())) {
      return "";
    }

    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return "Today";
    } else if (days === 1) {
      return "Yesterday";
    } else if (days < 7) {
      return `${days} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-pai-accent flex items-center justify-between">
        <h2 className="font-semibold">Conversations</h2>
        <button
          onClick={onNew}
          className="p-2 text-pai-muted hover:text-pai-highlight transition-colors"
          title="New chat"
        >
          <PlusIcon className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {chats.length === 0 ? (
          <div className="text-center py-8 text-pai-muted">
            <ChatBubbleLeftIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>No conversations yet</p>
            <p className="text-sm">Start a new chat!</p>
          </div>
        ) : (
          <ul className="space-y-1">
            {chats.map((chat) => (
              <li key={chat.chat_id}>
                <button
                  onClick={() => onSelect(chat.chat_id)}
                  className={`w-full text-left p-3 rounded-lg transition-colors group ${
                    selectedChat === chat.chat_id
                      ? "bg-pai-accent"
                      : "hover:bg-pai-accent/50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">
                        {chat.chat_name || `Chat ${chat.chat_id}`}
                      </p>
                      <p className="text-xs text-pai-muted">
                        {formatDate(chat.updated_at)}
                      </p>
                    </div>
                    {onDelete && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDelete(chat.chat_id);
                        }}
                        className="p-1 text-pai-muted hover:text-pai-highlight opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete chat"
                      >
                        <TrashIcon className="w-4 h-4" />
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
  );
}
