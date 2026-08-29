export interface HomeAssistantEntityState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
  last_updated: string;
  context?: Record<string, unknown>;
}

export interface HomeAssistantStateChangedEvent {
  entityId: string;
  oldState: HomeAssistantEntityState | null;
  newState: HomeAssistantEntityState | null;
  timeFired?: string;
}

export interface HomeAssistantStateSubscription {
  close(): void;
}

export interface HomeAssistantStateEventHandlers {
  onStateChanged(event: HomeAssistantStateChangedEvent): void;
  onDisconnect(error?: Error): void;
  onProtocolError?(error: Error): void;
}

export interface WebSocketLike {
  readonly readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  addEventListener(type: string, listener: (event: any) => void): void;
  removeEventListener(type: string, listener: (event: any) => void): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface HomeAssistantClientOptions {
  token: string;
  restBaseUrl?: string;
  websocketUrl?: string;
  fetch?: typeof fetch;
  webSocketFactory?: WebSocketFactory;
  requestTimeoutMs?: number;
  websocketTimeoutMs?: number;
  websocketHeartbeatMs?: number;
  websocketHeartbeatTimeoutMs?: number;
  setTimeout?: typeof setTimeout;
  clearTimeout?: typeof clearTimeout;
}

export interface HomeAssistantBinaryResponse {
  ok: boolean;
  status: number;
  headers: Headers;
  body: ReadableStream<Uint8Array> | null;
  arrayBuffer(): Promise<ArrayBuffer>;
}

export interface HomeAssistantClientLike {
  getStates(signal?: AbortSignal): Promise<HomeAssistantEntityState[]>;
  callService(
    domain: 'media_player',
    service: string,
    data: Record<string, unknown>
  ): Promise<unknown>;
  connectStateEvents(
    handlers: HomeAssistantStateEventHandlers,
    signal?: AbortSignal
  ): Promise<HomeAssistantStateSubscription>;
  fetchAuthenticatedPath(path: string): Promise<HomeAssistantBinaryResponse>;
}

export class HomeAssistantClientError extends Error {
  readonly code:
    | 'authentication'
    | 'http'
    | 'network'
    | 'protocol'
    | 'timeout'
    | 'cancelled';
  readonly statusCode?: number;

  constructor(
    code: HomeAssistantClientError['code'],
    message: string,
    statusCode?: number
  ) {
    super(message);
    this.name = 'HomeAssistantClientError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

const DEFAULT_REST_BASE_URL = 'http://supervisor/core/api';
const DEFAULT_WEBSOCKET_URL = 'ws://supervisor/core/websocket';
const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;
const DEFAULT_WEBSOCKET_TIMEOUT_MS = 8_000;
const DEFAULT_WEBSOCKET_HEARTBEAT_MS = 15_000;
const DEFAULT_WEBSOCKET_HEARTBEAT_TIMEOUT_MS = 45_000;

const withoutTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

const safeError = (error: unknown, fallback: string): Error => {
  if (error instanceof HomeAssistantClientError) {
    return error;
  }
  if (error instanceof Error && error.name === 'AbortError') {
    return new HomeAssistantClientError('timeout', fallback);
  }
  return new HomeAssistantClientError('network', fallback);
};

const cancellationError = (): HomeAssistantClientError =>
  new HomeAssistantClientError(
    'cancelled',
    'Home Assistant request was cancelled'
  );

const parseJsonObject = (value: unknown): Record<string, any> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, any>;
};

const defaultWebSocketFactory: WebSocketFactory = (url: string) => {
  if (typeof WebSocket === 'undefined') {
    throw new HomeAssistantClientError(
      'protocol',
      'WebSocket is unavailable in this runtime'
    );
  }
  return new WebSocket(url);
};

export class HomeAssistantClient implements HomeAssistantClientLike {
  private readonly token: string;
  private readonly restBaseUrl: string;
  private readonly coreBaseUrl: string;
  private readonly websocketUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly webSocketFactory: WebSocketFactory;
  private readonly requestTimeoutMs: number;
  private readonly websocketTimeoutMs: number;
  private readonly websocketHeartbeatMs: number;
  private readonly websocketHeartbeatTimeoutMs: number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;

  constructor(options: HomeAssistantClientOptions) {
    if (!options.token || !options.token.trim()) {
      throw new HomeAssistantClientError(
        'authentication',
        'SUPERVISOR_TOKEN is required for Home Assistant mode',
        401
      );
    }

    this.token = options.token;
    this.restBaseUrl = withoutTrailingSlash(
      options.restBaseUrl || DEFAULT_REST_BASE_URL
    );
    this.coreBaseUrl = this.restBaseUrl.replace(/\/api$/, '');
    this.websocketUrl = options.websocketUrl || DEFAULT_WEBSOCKET_URL;
    this.fetchImpl = options.fetch || fetch;
    this.webSocketFactory = options.webSocketFactory || defaultWebSocketFactory;
    this.requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
    this.websocketTimeoutMs =
      options.websocketTimeoutMs ?? DEFAULT_WEBSOCKET_TIMEOUT_MS;
    this.websocketHeartbeatMs =
      options.websocketHeartbeatMs ?? DEFAULT_WEBSOCKET_HEARTBEAT_MS;
    this.websocketHeartbeatTimeoutMs =
      options.websocketHeartbeatTimeoutMs ?? DEFAULT_WEBSOCKET_HEARTBEAT_TIMEOUT_MS;
    this.setTimer = options.setTimeout || setTimeout;
    this.clearTimer = options.clearTimeout || clearTimeout;
  }

  async getStates(signal?: AbortSignal): Promise<HomeAssistantEntityState[]> {
    const result = await this.requestJson('/states', {method: 'GET'}, signal);
    if (!Array.isArray(result)) {
      throw new HomeAssistantClientError(
        'protocol',
        'Home Assistant states response was not an array'
      );
    }
    return result as HomeAssistantEntityState[];
  }

  async callService(
    domain: 'media_player',
    service: string,
    data: Record<string, unknown>
  ): Promise<unknown> {
    if (!/^[a-z][a-z0-9_]*$/.test(service)) {
      throw new HomeAssistantClientError('protocol', 'Invalid Home Assistant service name');
    }
    return this.requestJson(`/services/${domain}/${service}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
  }

  async fetchAuthenticatedPath(path: string): Promise<HomeAssistantBinaryResponse> {
    if (!path.startsWith('/') || path.startsWith('//')) {
      throw new HomeAssistantClientError('protocol', 'Invalid Home Assistant path');
    }
    return this.request(`${this.coreBaseUrl}${path}`, {method: 'GET'});
  }

  connectStateEvents(
    handlers: HomeAssistantStateEventHandlers,
    signal?: AbortSignal
  ): Promise<HomeAssistantStateSubscription> {
    if (signal?.aborted) {
      return Promise.reject(cancellationError());
    }
    let socket: WebSocketLike;
    try {
      socket = this.webSocketFactory(this.websocketUrl);
    } catch (error) {
      return Promise.reject(safeError(error, 'Home Assistant WebSocket connection failed'));
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      let authenticated = false;
      let subscribed = false;
      let closedByClient = false;
      let disconnectNotified = false;
      const subscriptionId = 1;
      let nextMessageId = subscriptionId + 1;
      let pendingPingId: number | null = null;
      let handshakeTimer: ReturnType<typeof setTimeout> | null = null;
      let heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
      let livenessTimer: ReturnType<typeof setTimeout> | null = null;

      const cleanup = (): void => {
        if (handshakeTimer !== null) {
          this.clearTimer(handshakeTimer);
          handshakeTimer = null;
        }
        if (heartbeatTimer !== null) {
          this.clearTimer(heartbeatTimer);
          heartbeatTimer = null;
        }
        if (livenessTimer !== null) {
          this.clearTimer(livenessTimer);
          livenessTimer = null;
        }
        socket.removeEventListener('message', onMessage);
        socket.removeEventListener('error', onError);
        socket.removeEventListener('close', onClose);
        signal?.removeEventListener('abort', onAbort);
      };

      const closeFromClient = (reason: string): void => {
        if (closedByClient) {
          return;
        }
        closedByClient = true;
        cleanup();
        try {
          socket.close(1000, reason);
        } catch (_error) {
          // The socket may already be closed.
        }
      };

      const onAbort = (): void => {
        if (closedByClient) {
          return;
        }
        const pending = !settled;
        if (pending) {
          settled = true;
        }
        closeFromClient('cancelled');
        if (pending) {
          reject(cancellationError());
        }
      };

      const notifyDisconnect = (error?: Error): void => {
        if (closedByClient || disconnectNotified) {
          return;
        }
        disconnectNotified = true;
        cleanup();
        handlers.onDisconnect(error);
      };

      const schedulePing = (): void => {
        if (closedByClient || !subscribed) {
          return;
        }
        if (heartbeatTimer !== null) {
          this.clearTimer(heartbeatTimer);
        }
        heartbeatTimer = this.setTimer(() => {
          heartbeatTimer = null;
          const pingId = nextMessageId++;
          pendingPingId = pingId;
          socket.send(JSON.stringify({id: pingId, type: 'ping'}));
        }, this.websocketHeartbeatMs);
      };

      const acceptLiveness = (): void => {
        if (closedByClient || !subscribed || disconnectNotified) {
          return;
        }
        pendingPingId = null;
        if (livenessTimer !== null) {
          this.clearTimer(livenessTimer);
        }
        livenessTimer = this.setTimer(() => {
          livenessTimer = null;
          const error = new HomeAssistantClientError(
            'timeout',
            'Home Assistant WebSocket liveness timed out'
          );
          notifyDisconnect(error);
          try {
            socket.close(4000, 'heartbeat timeout');
          } catch (_error) {
            // The socket may already be closed.
          }
        }, this.websocketHeartbeatTimeoutMs);
        schedulePing();
      };

      const failBeforeReady = (error: Error): void => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        try {
          socket.close(1000, 'connection failed');
        } catch (_error) {
          // The connection may already be closed.
        }
        reject(error);
      };

      const onMessage = (event: any): void => {
        let message: Record<string, any> | null = null;
        try {
          message = parseJsonObject(JSON.parse(String(event.data)));
        } catch (_error) {
          const error = new HomeAssistantClientError(
            'protocol',
            'Home Assistant WebSocket sent invalid JSON'
          );
          if (!settled) {
            failBeforeReady(error);
          } else {
            handlers.onProtocolError?.(error);
          }
          return;
        }

        if (!message) {
          return;
        }
        if (message.type === 'pong' && message.id === pendingPingId) {
          acceptLiveness();
          return;
        }
        if (message.type === 'auth_required') {
          socket.send(JSON.stringify({type: 'auth', access_token: this.token}));
          return;
        }
        if (message.type === 'auth_invalid') {
          failBeforeReady(new HomeAssistantClientError(
            'authentication',
            'Home Assistant WebSocket authentication was rejected',
            401
          ));
          return;
        }
        if (message.type === 'auth_ok' && !authenticated) {
          authenticated = true;
          socket.send(JSON.stringify({
            id: subscriptionId,
            type: 'subscribe_events',
            event_type: 'state_changed',
          }));
          return;
        }
        if (
          message.type === 'result' &&
          message.id === subscriptionId &&
          !subscribed
        ) {
          if (message.success !== true) {
            failBeforeReady(new HomeAssistantClientError(
              'protocol',
              'Home Assistant rejected the state subscription'
            ));
            return;
          }
          subscribed = true;
          settled = true;
          if (handshakeTimer !== null) {
            this.clearTimer(handshakeTimer);
            handshakeTimer = null;
          }
          acceptLiveness();
          resolve({
            close: (): void => closeFromClient('shutdown'),
          });
          return;
        }
        if (message.type !== 'event' || message.id !== subscriptionId) {
          return;
        }

        const eventObject = parseJsonObject(message.event);
        const data = parseJsonObject(eventObject?.data);
        if (!eventObject || !data || typeof data.entity_id !== 'string') {
          handlers.onProtocolError?.(new HomeAssistantClientError(
            'protocol',
            'Home Assistant state event was malformed'
          ));
          return;
        }
        acceptLiveness();
        handlers.onStateChanged({
          entityId: data.entity_id,
          oldState: (data.old_state || null) as HomeAssistantEntityState | null,
          newState: (data.new_state || null) as HomeAssistantEntityState | null,
          timeFired: typeof eventObject.time_fired === 'string'
            ? eventObject.time_fired
            : undefined,
        });
      };

      const onError = (): void => {
        const error = new HomeAssistantClientError(
          'network',
          'Home Assistant WebSocket failed'
        );
        if (!settled) {
          failBeforeReady(error);
        } else {
          notifyDisconnect(error);
          try {
            socket.close(1011, 'socket error');
          } catch (_error) {
            // The socket may already be closed.
          }
        }
      };

      const onClose = (): void => {
        if (!settled) {
          failBeforeReady(new HomeAssistantClientError(
            'network',
            'Home Assistant WebSocket closed before subscription'
          ));
        } else {
          notifyDisconnect();
        }
      };

      socket.addEventListener('message', onMessage);
      socket.addEventListener('error', onError);
      socket.addEventListener('close', onClose);

      handshakeTimer = this.setTimer(() => {
        failBeforeReady(new HomeAssistantClientError(
          'timeout',
          'Home Assistant WebSocket subscription timed out'
        ));
      }, this.websocketTimeoutMs);
      signal?.addEventListener('abort', onAbort, {once: true});
      if (signal?.aborted) {
        onAbort();
      }
    });
  }

  private async requestJson(
    path: string,
    init: RequestInit,
    signal?: AbortSignal
  ): Promise<unknown> {
    const response = await this.request(`${this.restBaseUrl}${path}`, init, signal);
    try {
      return await (response as Response).json();
    } catch (error) {
      if (error instanceof HomeAssistantClientError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new HomeAssistantClientError(
          'timeout',
          'Home Assistant request timed out before the response completed'
        );
      }
      throw new HomeAssistantClientError(
        'protocol',
        'Home Assistant returned invalid JSON'
      );
    }
  }

  private async request(
    url: string,
    init: RequestInit,
    signal?: AbortSignal
  ): Promise<Response> {
    if (signal?.aborted) {
      throw cancellationError();
    }
    const controller = new AbortController();
    let timedOut = false;
    let cancelled = false;
    let released = false;
    let bodyReader: ReadableStreamDefaultReader<Uint8Array> | null = null;
    let bodyController: ReadableStreamDefaultController<Uint8Array> | null = null;
    const timeoutError = (): HomeAssistantClientError => new HomeAssistantClientError(
      'timeout',
      'Home Assistant request timed out before the response completed'
    );
    let timeout: ReturnType<typeof setTimeout> | null = null;
    const releaseRequest = (): void => {
      if (released) {
        return;
      }
      released = true;
      if (timeout !== null) {
        this.clearTimer(timeout);
        timeout = null;
      }
      signal?.removeEventListener('abort', onAbort);
    };
    const abortRequest = (error: HomeAssistantClientError): void => {
      if (timedOut || cancelled || released) {
        return;
      }
      timedOut = error.code === 'timeout';
      cancelled = error.code === 'cancelled';
      controller.abort();
      bodyController?.error(error);
      void bodyReader?.cancel(error).catch(() => undefined);
      releaseRequest();
    };
    const onAbort = (): void => abortRequest(cancellationError());
    signal?.addEventListener('abort', onAbort, {once: true});
    if (signal?.aborted) {
      onAbort();
    }
    if (cancelled) {
      throw cancellationError();
    }
    timeout = this.setTimer(
      () => abortRequest(timeoutError()),
      this.requestTimeoutMs
    );

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        ...init,
        redirect: 'error',
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${this.token}`,
          ...(init.headers || {}),
        },
      });
      if (timedOut || cancelled) {
        throw cancelled ? cancellationError() : timeoutError();
      }
      if (!response.ok) {
        const authentication = response.status === 401 || response.status === 403;
        controller.abort();
        void response.body?.cancel().catch(() => undefined);
        throw new HomeAssistantClientError(
          authentication ? 'authentication' : 'http',
          `Home Assistant request failed with status ${response.status}`,
          response.status
        );
      }
    } catch (error) {
      releaseRequest();
      if (timedOut || cancelled) {
        throw cancelled ? cancellationError() : timeoutError();
      }
      throw safeError(error, 'Home Assistant request failed');
    }

    if (!response.body) {
      releaseRequest();
      return response;
    }

    bodyReader = response.body.getReader();
    const body = new ReadableStream<Uint8Array>({
      start: streamController => {
        bodyController = streamController;
      },
      pull: async streamController => {
        try {
          const chunk = await bodyReader!.read();
          if (chunk.done) {
            releaseRequest();
            bodyController = null;
            streamController.close();
            return;
          }
          streamController.enqueue(chunk.value);
        } catch (error) {
          releaseRequest();
          bodyController = null;
          if (!timedOut && !cancelled) {
            streamController.error(safeError(
              error,
              'Home Assistant response body failed'
            ));
          }
        }
      },
      cancel: async reason => {
        releaseRequest();
        bodyController = null;
        try {
          await bodyReader!.cancel(reason);
        } catch (_error) {
          // Cancellation is best effort after the caller has abandoned the body.
        }
      },
    });

    return new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  }
}
