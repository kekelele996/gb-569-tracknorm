/** 轻量 toast 队列（useSyncExternalStore）。 */
export interface Toast {
  id: number;
  text: string;
  tone: 'ok' | 'error';
}

type Listener = () => void;

class UiStore {
  private toasts: Toast[] = [];
  private listeners = new Set<Listener>();
  private seq = 0;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getToasts = (): Toast[] => this.toasts;

  push(text: string, tone: Toast['tone'] = 'ok') {
    const id = ++this.seq;
    this.toasts = [...this.toasts, { id, text, tone }];
    this.listeners.forEach((listener) => listener());
    setTimeout(() => this.dismiss(id), 4200);
  }

  dismiss(id: number) {
    this.toasts = this.toasts.filter((toast) => toast.id !== id);
    this.listeners.forEach((listener) => listener());
  }
}

export const uiStore = new UiStore();
