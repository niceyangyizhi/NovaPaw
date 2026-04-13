import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
  IAgentScopeRuntimeWebUIRef,
} from "@agentscope-ai/chat";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Modal, Button, Result, GetProp, Upload, Image } from "antd";
import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import "./index.module.less";
import sessionApi from "./sessionApi";
import defaultConfig, { getDefaultConfig } from "./OptionsPanel/defaultConfig";
import Weather from "./Weather";
import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import ModelSelector from "./ModelSelector";

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

const DEFAULT_SESSION_NAME = "New Chat";

function buildModelError(): Response {
  return new Response(
    JSON.stringify({
      error: "Model not configured",
      message: "Please configure a model first",
    }),
    { status: 400, headers: { "Content-Type": "application/json" } },
  );
}

// Convert file to base64 data URL
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const chatId = useMemo(() => {
    const match = location.pathname.match(/^\/chat\/(.+)$/);
    return match?.[1];
  }, [location.pathname]);
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [hasActiveSession, setHasActiveSession] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const chatUiRef = useRef<IAgentScopeRuntimeWebUIRef>(null);
  // Store original full-resolution images as array (most recent first)
  const originalImagesRef = useRef<string[]>([]);

  // Disable input for historical sessions, and navigate to today's session if none selected
  useEffect(() => {
    const checkSessionActive = async () => {
      try {
        const sessions = await sessionApi.getSessionList();
        
        // If no session ID specified, navigate to today's active session
        if (!chatId) {
          const todaySession = sessions.find(s => (s as any).isActive === true);
          if (todaySession) {
            navigate(`/chat/${todaySession.id}`, { replace: true });
          }
          return;
        }
        
        if (!chatUiRef.current) return;
        
        // Check if current session is active and disable input if not
        const currentSession = sessions.find(s => s.id === chatId);
        const isActive = currentSession ? (currentSession as any).isActive === true : true;
        chatUiRef.current?.input?.setDisabled?.(!isActive);
      } catch (e) {
        console.error("Failed to check session active status:", e);
      }
    };
    
    checkSessionActive();
  }, [chatId, navigate]);

  // Re-check session active status when component mounts and when chatId changes
  useEffect(() => {
    const checkSessionActive = async () => {
      try {
        const sessions = await sessionApi.getSessionList();
        
        // Update hasActiveSession state
        const activeSession = sessions.find(s => (s as any).isActive === true);
        setHasActiveSession(!!activeSession);
        
        if (!chatId || !chatUiRef.current) return;
        
        // Check if current session is active and disable input if not
        const currentSession = sessions.find(s => s.id === chatId);
        const isActive = currentSession ? (currentSession as any).isActive === true : true;
        chatUiRef.current?.input?.setDisabled?.(!isActive);
      } catch (e) {
        console.error("Failed to check session active status:", e);
      }
    };
    
    checkSessionActive();
  }, [chatId]);

  useEffect(() => {
    const styleId = "novapaw-input-attachment-preview-style";
    let styleEl = document.getElementById(styleId) as HTMLStyleElement | null;

    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = styleId;
      styleEl.textContent = `
        [class*="attachment-list-card-type-preview"] {
          position: relative;
          display: block;
          border-radius: 8px;
        }

        [class*="attachment-list-card-type-preview"] img {
          border-radius: 8px;
          cursor: pointer;
        }

        [class*="attachment-list-card-hoverable"][class*="attachment-list-card-type-preview"]:hover::after {
          background:
            url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z'/%3E%3C/svg%3E")
              center / 24px 24px no-repeat,
            rgba(0, 0, 0, 0.45) !important;
          background-position: center !important;
          background-repeat: no-repeat !important;
          background-size: 24px 24px !important;
          opacity: 1 !important;
        }
      `;
      document.head.appendChild(styleEl);
    }

    return () => {
      styleEl?.remove();
    };
  }, []);

  useEffect(() => {
    // Handle click on attachment thumbnails to preview full image
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;

      // Find the closest attachment container or image
      const attachmentContainer = target.closest(
        '[class*="attachment"], [class*="Attachment"], [class*="attachments"]',
      );

      // Must be in sender area, not conversation
      const senderArea = target.closest('[class*="sender"], [class*="Sender"]');

      if (attachmentContainer && senderArea) {
        // Find the image inside the attachment container
        const img = attachmentContainer.querySelector(
          "img",
        ) as HTMLImageElement;
        if (img?.src) {
          e.preventDefault();
          e.stopPropagation();

          // Try to find original full-resolution image
          let fullResUrl = img.src;

          // Find all attachment images to determine index
          const allAttachments = senderArea.querySelectorAll(
            '[class*="attachment"] img, [class*="Attachment"] img',
          );
          const attachmentIndex = Array.from(allAttachments).indexOf(img);

          // Use stored original by index (stored in reverse order)
          const storedImages = originalImagesRef.current;
          if (storedImages.length > 0) {
            // Images are stored most-recent-first, but displayed in upload order
            // So reverse the index: last stored = first displayed
            const reverseIndex = storedImages.length - 1 - attachmentIndex;
            if (reverseIndex >= 0 && reverseIndex < storedImages.length) {
              fullResUrl = storedImages[reverseIndex];
            } else if (storedImages.length === 1) {
              // If only one image stored, use it
              fullResUrl = storedImages[0];
            }
          }

          setPreviewImage(fullResUrl);
        }
      }
    };

    document.addEventListener("click", handleClick, true);
    return () => {
      document.removeEventListener("click", handleClick, true);
    };
  }, []);

  // Custom upload handler for clipboard paste and file attachments
  const customUploadRequest: GetProp<typeof Upload, "customRequest"> =
    useCallback(async (options) => {
      const { file, onSuccess, onError, onProgress } = options;
      try {
        onProgress?.({ percent: 30 });
        const base64Url = await fileToBase64(file as File);
        onProgress?.({ percent: 100 });

        // Store original full-resolution image (most recent first)
        originalImagesRef.current.unshift(base64Url);
        // Keep only last 10 images to prevent memory leak
        if (originalImagesRef.current.length > 10) {
          originalImagesRef.current.pop();
        }

        // Return the base64 URL - this will be used as image_url in message content
        onSuccess?.({ url: base64Url });
      } catch (error) {
        onError?.(error as Error);
      }
    }, []);

  const isComposingRef = useRef(false);
  const isChatActiveRef = useRef(false);
  isChatActiveRef.current =
    location.pathname === "/" || location.pathname.startsWith("/chat");

  const lastSessionIdRef = useRef<string | null>(null);
  const chatIdRef = useRef(chatId);
  const navigateRef = useRef(navigate);
  chatIdRef.current = chatId;
  navigateRef.current = navigate;

  useEffect(() => {
    const handleCompositionStart = () => {
      if (!isChatActiveRef.current) return;
      isComposingRef.current = true;
    };

    const handleCompositionEnd = () => {
      if (!isChatActiveRef.current) return;
      setTimeout(() => {
        isComposingRef.current = false;
      }, 150);
    };

    const handleKeyPress = (e: KeyboardEvent) => {
      if (!isChatActiveRef.current) return;
      const target = e.target as HTMLElement;
      if (target?.tagName === "TEXTAREA" && e.key === "Enter" && !e.shiftKey) {
        if (isComposingRef.current || (e as any).isComposing) {
          e.stopPropagation();
          e.stopImmediatePropagation();
          return false;
        }
      }
    };

    document.addEventListener("compositionstart", handleCompositionStart, true);
    document.addEventListener("compositionend", handleCompositionEnd, true);
    document.addEventListener("keypress", handleKeyPress, true);

    return () => {
      document.removeEventListener(
        "compositionstart",
        handleCompositionStart,
        true,
      );
      document.removeEventListener(
        "compositionend",
        handleCompositionEnd,
        true,
      );
      document.removeEventListener("keypress", handleKeyPress, true);
    };
  }, []);

  useEffect(() => {
    sessionApi.onSessionIdResolved = (tempId, realId) => {
      if (!isChatActiveRef.current) return;
      if (chatIdRef.current === tempId) {
        lastSessionIdRef.current = realId;
        navigateRef.current(`/chat/${realId}`, { replace: true });
      }
    };

    sessionApi.onSessionRemoved = (removedId) => {
      if (!isChatActiveRef.current) return;
      if (chatIdRef.current === removedId) {
        lastSessionIdRef.current = null;
        navigateRef.current("/chat", { replace: true });
      }
    };

    return () => {
      sessionApi.onSessionIdResolved = null;
      sessionApi.onSessionRemoved = null;
    };
  }, []);

  const getSessionListWrapped = useCallback(async () => {
    const sessions = await sessionApi.getSessionList();
    const currentChatId = chatIdRef.current;

    const activeIdx = sessions.findIndex((s) => (s as any).isActive === true);
    if (activeIdx >= 0) {
      if (activeIdx === 0) return sessions;
      return [
        sessions[activeIdx],
        ...sessions.slice(0, activeIdx),
        ...sessions.slice(activeIdx + 1),
      ];
    }

    if (currentChatId) {
      const idx = sessions.findIndex((s) => s.id === currentChatId);
      if (idx > 0) {
        return [
          sessions[idx],
          ...sessions.slice(0, idx),
          ...sessions.slice(idx + 1),
        ];
      }
    }

    return sessions;
  }, []);

  const getSessionWrapped = useCallback(async (sessionId: string) => {
    const currentChatId = chatIdRef.current;

    if (
      isChatActiveRef.current &&
      sessionId &&
      sessionId !== lastSessionIdRef.current &&
      sessionId !== currentChatId
    ) {
      const urlId = sessionApi.getRealIdForSession(sessionId) ?? sessionId;
      lastSessionIdRef.current = urlId;
      navigateRef.current(`/chat/${urlId}`, { replace: true });
    }

    return sessionApi.getSession(sessionId);
  }, []);

  // Session creation is enabled only when today's session doesn't exist
  const wrappedSessionApi = useMemo(
    () => ({
      getSessionList: getSessionListWrapped,
      getSession: getSessionWrapped,
      createSession: async (session: any) => {
        console.log("createSession called");
        try {
          // First get the latest session list from backend to check for active session
          console.log("Getting session list...");
          const sessions = await sessionApi.getSessionList();
          console.log("Session list received:", sessions);
          
          const activeSession = sessions.find(s => (s as any).isActive === true);
          console.log("Active session found:", activeSession);
          
          if (activeSession) {
            // Today's session already exists, don't create a new one
            console.log("Today's session already exists, skipping creation");
            return sessions;
          }
          
          // Today's session doesn't exist, allow creation
          console.log("Creating new session for today");
          const result = await sessionApi.createSession(session);
          console.log("Session created:", result);
          return result;
        } catch (error) {
          console.error("Error in createSession:", error);
          // Return current session list in case of error
          return sessionApi.sessionList;
        }
      },
      updateSession: sessionApi.updateSession.bind(sessionApi),
      removeSession: sessionApi.removeSession.bind(sessionApi),
    }),
    [getSessionListWrapped, getSessionWrapped, hasActiveSession],
  );

  const ensureWritableConsoleSession = useCallback(async () => {
    let sessions = await sessionApi.getSessionList();
    let activeSession = sessions.find(
      (s) => (s as any).isActive === true,
    ) as any | undefined;

    if (!activeSession) {
      await sessionApi.createSession({ name: DEFAULT_SESSION_NAME });
      sessions = await sessionApi.getSessionList();
      activeSession = sessions.find(
        (s) => (s as any).isActive === true,
      ) as any | undefined;
    }

    if (!activeSession) return null;

    const targetChatId = activeSession.realId ?? activeSession.id;
    const currentChatId = chatIdRef.current;

    window.currentSessionId = activeSession.sessionId || "";
    window.currentUserId = activeSession.userId || "default";
    window.currentChannel = activeSession.channel || "console";

    if (
      isChatActiveRef.current &&
      targetChatId &&
      currentChatId !== targetChatId
    ) {
      lastSessionIdRef.current = targetChatId;
      navigateRef.current(`/chat/${targetChatId}`, { replace: true });
    }

    return activeSession;
  }, []);

  const customFetch = useCallback(
    async (data: {
      input: any[];
      biz_params?: any;
      signal?: AbortSignal;
    }): Promise<Response> => {
      try {
        const activeModels = await providerApi.getActiveModels();
        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          setShowModelPrompt(true);
          return buildModelError();
        }
      } catch {
        setShowModelPrompt(true);
        return buildModelError();
      }

      const { input, biz_params } = data;
      const session = input[input.length - 1]?.session || {};
      const writableSession = await ensureWritableConsoleSession();

      const requestBody = {
        input: input.slice(-1),
        session_id:
          writableSession?.sessionId ||
          window.currentSessionId ||
          session?.session_id ||
          "",
        user_id:
          writableSession?.userId ||
          window.currentUserId ||
          session?.user_id ||
          "default",
        channel:
          writableSession?.channel ||
          window.currentChannel ||
          session?.channel ||
          "console",
        stream: true,
        ...biz_params,
      };

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const token = getApiToken();
      if (token) headers.Authorization = `Bearer ${token}`;

      return fetch(defaultConfig?.api?.baseURL || getApiUrl("/agent/process"), {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });
    },
    [ensureWritableConsoleSession],
  );

  const options = useMemo(() => {
    const i18nConfig = getDefaultConfig(t);

    const handleBeforeSubmit = async () => {
      if (isComposingRef.current) return false;
      return true;
    };

    return {
      ...i18nConfig,
      theme: {
        ...defaultConfig.theme,
        rightHeader: <ModelSelector />,
      },
      sender: {
        ...(i18nConfig as any)?.sender,
        beforeSubmit: handleBeforeSubmit,
        attachments: {
          accept: "image/*,.png,.jpg,.jpeg,.gif,.webp,.bmp",
          multiple: true,
          customRequest: customUploadRequest,
        },
      },
      session: { multiple: true, api: wrappedSessionApi, create: !hasActiveSession },
      api: {
        ...defaultConfig.api,
        fetch: customFetch,
        cancel(data: { session_id: string }) {
          console.log(data);
        },
      },
      customToolRenderConfig: {
        "weather search mock": Weather,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [wrappedSessionApi, customFetch, t, customUploadRequest, hasActiveSession]);

  return (
    <div ref={containerRef} style={{ height: "100%", width: "100%" }}>
      <AgentScopeRuntimeWebUI ref={chatUiRef} options={options} />

      <Modal open={showModelPrompt} closable={false} footer={null} width={480}>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
          title={t("modelConfig.promptTitle")}
          subTitle={t("modelConfig.promptMessage")}
          extra={[
            <Button key="skip" onClick={() => setShowModelPrompt(false)}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={() => {
                setShowModelPrompt(false);
                navigate("/models");
              }}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>

      {/* Image preview modal for attachment thumbnails */}
      <Image
        style={{ display: "none" }}
        preview={{
          visible: !!previewImage,
          src: previewImage || "",
          onVisibleChange: (visible) => {
            if (!visible) setPreviewImage(null);
          },
        }}
      />
    </div>
  );
}
