import type { Catalog } from "../lib/api";
import AutomationCard from "./AutomationCard";

export default function CatalogGrid({
  catalog,
  activeIds,
}: {
  catalog: Catalog;
  activeIds: Set<string>;
}) {
  return (
    <div className="flex flex-col gap-12">
      {catalog.categories.map((category) => {
        const items = catalog.automations.filter(
          (item) => item.category === category.key,
        );
        if (items.length === 0) {
          return null;
        }
        return (
          <section key={category.key}>
            <div className="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line pb-3">
              <h2 className="font-display text-lg font-semibold text-text">
                {category.title}
              </h2>
              <p className="text-sm text-text-dim">{category.summary}</p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((automation) => (
                <AutomationCard
                  key={automation.id}
                  automation={automation}
                  active={activeIds.has(automation.id)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
