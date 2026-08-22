import {
  Archive,
  Boxes,
  CheckSquare,
  Code2,
  FileText,
  FolderTree,
  Globe,
  LayoutDashboard,
  Mail,
  MessageCircle,
  MonitorPlay,
  MousePointerClick,
  RefreshCw,
  Send,
  type LucideIcon,
} from "lucide-react";

// Cada automacao real do catalogo recebe um icone proprio (parte do visual).
const AUTOMATION_ICONS: Record<string, LucideIcon> = {
  validate: CheckSquare,
  backup: Archive,
  organize: FolderTree,
  extract_web: Globe,
  extract_api: Code2,
  send_api: Send,
  send_telegram: MessageCircle,
  sync_api: RefreshCw,
  send_email: Mail,
  extract_web_js: MonitorPlay,
  rpa_cadastro: MousePointerClick,
  report: FileText,
  dashboard: LayoutDashboard,
};

export function iconFor(id: string): LucideIcon {
  return AUTOMATION_ICONS[id] ?? Boxes;
}
