import { useEffect } from "react";

type Props = {
  isOpen: boolean;
  title: string;
  fileUrl: string | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
};

export function DocumentPreviewModal({ isOpen, title, fileUrl, loading, error, onClose }: Props) {
  useEffect(() => {
    function onEsc(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    if (isOpen) {
      window.addEventListener("keydown", onEsc);
    }

    return () => {
      window.removeEventListener("keydown", onEsc);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="mini-btn" onClick={onClose}>Close</button>
        </div>

        <div className="modal-body">
          {loading && <p className="hint">Loading document...</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && fileUrl && (
            <iframe src={fileUrl} title={title} className="doc-frame" />
          )}
        </div>
      </div>
    </div>
  );
}