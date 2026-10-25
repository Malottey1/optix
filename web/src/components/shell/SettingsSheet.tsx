import { Link } from "react-router";
import { Icon } from "../../icons";
import { LANG_NAMES, useT } from "../../lib/i18n";
import { setSetting, useSettings } from "../../state/settings";
import { LANGS, type Lang } from "../../types/ui";
import { Segmented } from "../ui/segmented";
import { Sheet } from "../ui/sheet";
import { Switch } from "../ui/switch";

export function SettingsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { t } = useT();
  const s = useSettings();
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      id="settings"
      title={t("settings")}
      closeLabel={t("close")}
      width="max-w-[400px]"
    >
      <Link
        to="/tech"
        data-settings-tech
        onClick={() => onOpenChange(false)}
        className="mb-6 flex min-h-[52px] items-center gap-3 rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 hover:border-accent-line"
      >
        <Icon name="tech" size={22} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] font-semibold text-ink">{t("tech_details")}</span>
          <span className="block text-[12px] text-ink-3">{t("tech_details_sub")}</span>
        </span>
        <span aria-hidden="true" className="text-ink-3">
          →
        </span>
      </Link>
      <section aria-labelledby="set-lang-h">
        <h3 id="set-lang-h" className="eyebrow">
          {t("language")}
        </h3>
        <Segmented<Lang>
          label={t("language")}
          name="lang"
          size="md"
          className="mt-2.5 w-full [&>button]:flex-1"
          value={s.lang}
          onChange={(v) => setSetting("lang", v)}
          options={LANGS.map((l) => ({ value: l, label: LANG_NAMES[l] }))}
        />
        <p className="mt-3 rounded-xl border border-line bg-surface-2 px-3.5 py-3 text-[12.5px] leading-relaxed text-ink-2">
          {t("english_only")}
        </p>
      </section>
      <section aria-labelledby="set-display-h" className="mt-6">
        <h3 id="set-display-h" className="eyebrow">
          {t("display")}
        </h3>
        <div className="mt-1 divide-y divide-line border-y border-line">
          <Switch
            id="set-motion"
            label={t("reduced_motion")}
            checked={s.reducedMotion}
            onChange={(v) => setSetting("reducedMotion", v)}
          />
          <Switch
            id="set-evidence"
            label={t("evidence_default")}
            checked={s.evidenceOpen}
            onChange={(v) => setSetting("evidenceOpen", v)}
          />
          <Switch
            id="set-contrast"
            label={t("high_contrast")}
            checked={s.highContrast}
            onChange={(v) => setSetting("highContrast", v)}
          />
          <div className="flex items-center justify-between gap-4 py-3">
            <span className="text-[14px] text-ink">{t("density")}</span>
            <Segmented
              label={t("density")}
              name="density"
              value={s.density}
              onChange={(v) => setSetting("density", v)}
              options={[
                { value: "comfortable", label: t("comfortable") },
                { value: "compact", label: t("compact") },
              ]}
            />
          </div>
        </div>
      </section>
      <p className="mt-5 text-[12.5px] leading-relaxed text-ink-3">{t("settings_note")}</p>
      <p className="mt-2 text-[12.5px] leading-relaxed text-ink-3" data-kits-note>
        {t("kits_note")}
      </p>
    </Sheet>
  );
}
