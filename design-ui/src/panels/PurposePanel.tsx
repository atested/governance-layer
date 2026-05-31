import type { PurposeItem } from "../types/design";
import type { ItemDraft } from "./types";

export type PurposePanelProps = {
  items: PurposeItem[];
  draft: ItemDraft;
  setDraft: (draft: ItemDraft) => void;
  onCreate: () => Promise<void>;
  onEdit: (item: PurposeItem) => Promise<void>;
  onShowLineage: (item: PurposeItem) => Promise<void>;
  onDemote: (item: PurposeItem) => Promise<void>;
};

export function PurposePanel({
  items,
  draft,
  setDraft,
  onCreate,
  onEdit,
  onShowLineage,
  onDemote
}: PurposePanelProps) {
  return (
    <section className="design-surface" data-testid="purpose-surface">
      <h2>Purpose</h2>
      <form
        className="item-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onCreate();
        }}
      >
        <input
          aria-label="Purpose title"
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          placeholder="Purpose candidate, constraint, boundary..."
          value={draft.title}
        />
        <textarea
          aria-label="Purpose body"
          onChange={(event) => setDraft({ ...draft, body: event.target.value })}
          placeholder="Purpose notes"
          value={draft.body}
        />
        <button type="submit">Add Purpose</button>
      </form>
      <div className="item-list">
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <input
              aria-label={`Edit purpose ${item.id}`}
              defaultValue={item.title}
              onBlur={(event) => void onEdit({ ...item, title: event.target.value })}
            />
            <p>{item.body || item.purposeType}</p>
            <div className="item-actions">
              <span>{item.state}</span>
              <button type="button" onClick={() => void onShowLineage(item)}>
                Lineage
              </button>
              <button type="button" onClick={() => void onDemote(item)}>
                Demote
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
