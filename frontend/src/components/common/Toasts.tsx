import { useSyncExternalStore } from 'react';
import { uiStore } from '../../stores/uiStore';

export default function Toasts() {
  const toasts = useSyncExternalStore(uiStore.subscribe, uiStore.getToasts);
  if (toasts.length === 0) return null;
  return (
    <div className="toasts">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast${toast.tone === 'error' ? ' error' : ''}`}>
          {toast.text}
        </div>
      ))}
    </div>
  );
}
