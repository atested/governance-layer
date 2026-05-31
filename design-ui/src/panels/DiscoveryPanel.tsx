import type { DiscoveryItem } from "../types/design";
import type { ItemDraft } from "./types";

export type DiscoveryPanelProps = {
  items: DiscoveryItem[];
  draft: ItemDraft;
  setDraft: (draft: ItemDraft) => void;
  onCreate: () => Promise<void>;
  onEdit: (item: DiscoveryItem) => Promise<void>;
  onShowLineage: (item: DiscoveryItem) => Promise<void>;
  onPromote: (item: DiscoveryItem) => Promise<void>;
};

export function DiscoveryPanel({
  items,
  draft,
  setDraft,
  onCreate,
  onEdit,
  onShowLineage,
  onPromote
}: DiscoveryPanelProps) {
  return (
    <section className="design-surface" data-testid="discovery-surface">
      <h2>Discovery</h2>
      <form
        className="item-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onCreate();
        }}
      >
        <input
          aria-label="Discovery title"
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          placeholder="Observation, question, anomaly..."
          value={draft.title}
        />
        <textarea
          aria-label="Discovery body"
          onChange={(event) => setDraft({ ...draft, body: event.target.value })}
          placeholder="Discovery notes"
          value={draft.body}
        />
        <button type="submit">Add Discovery</button>
      </form>
      <div className="item-list">
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <input
              aria-label={`Edit discovery ${item.id}`}
              defaultValue={item.title}
              onBlur={(event) => void onEdit({ ...item, title: event.target.value })}
            />
            <p>{item.body || item.discoveryType}</p>
            <div className="item-actions">
              <span>{item.state}</span>
              <button type="button" onClick={() => void onShowLineage(item)}>
                Lineage
              </button>
              <button type="button" onClick={() => void onPromote(item)}>
                Promote
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
