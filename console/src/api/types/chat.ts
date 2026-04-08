export interface ChatSpec {
  id: string; // Chat UUID identifier
  session_id: string; // Session identifier (daily active session id)
  user_id: string; // User identifier
  channel: string; // Channel name, default: "default"
  name?: string; // Chat name
  created_at: string | null; // Chat creation timestamp (ISO 8601)
  updated_at: string | null; // Chat last update timestamp (ISO 8601)
  meta?: Record<string, unknown>; // Additional metadata
  is_active?: boolean; // Whether this session is the current active session
}

export interface Message {
  role: string;
  content: unknown;
  [key: string]: unknown;
}

export interface ChatHistory {
  messages: Message[];
}

export interface ActiveSession {
  session_id: string;
  date: string;
  updated_at: string;
}

export interface ChatDeleteResponse {
  success: boolean;
  chat_id: string;
}

// Legacy Session type alias for backward compatibility
export type Session = ChatSpec;
