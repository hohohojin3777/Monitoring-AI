import type { Timestamp } from "firebase/firestore";

export type Grade = "red" | "orange" | "yellow" | "none";
export type FilterTag = "전체" | "대응필요" | "주의" | "위기" | "재발";
export type Role = "admin" | "member";

export interface Member {
  uid: string;
  role: Role;
  email: string;
  displayName?: string;
}

export interface ClusterStats {
  posts: number;
  platforms: string[];
  platformCount: number;
  likes: number;
  comments: number;
  views: number;
  sentiment: { positive: number; neutral: number; negative: number; attack: number };
}

export interface Cluster {
  id: string;
  title: string;
  summary?: string;
  grade: Grade;
  patterns: string[];
  filterTag: FilterTag;
  status: "active" | "resolved" | "archived";
  reactivated?: boolean;
  itemCount: number;
  firstSeen?: Timestamp;
  lastSeen?: Timestamp;
  stats?: ClusterStats;
}

export interface Item {
  id: string;
  platform: string;
  sourceType: string;
  url: string;
  title: string;
  content?: string;
  author?: string;
  sentiment?: string;
  publishedAt?: Timestamp;
  metrics?: { views?: number; likes?: number; comments?: number };
}

export interface ResponseStep {
  order: number;
  text: string;
  assigneeRole?: Role;
  done?: boolean;
}

export interface ResponseLink {
  title: string;
  url: string;
}

export interface CampResponse {
  id: string;
  createdBy: string;
  createdAt?: Timestamp;
  status: "draft" | "published";
  plan: string;
  steps: ResponseStep[];
  links: ResponseLink[];
  lawCheckRequired?: boolean;
  aiSuggested?: boolean;
}

export interface Ack {
  uid: string;
  displayName?: string;
  readAt?: Timestamp;
  clickedLinks?: string[];
  status?: "read" | "acted";
}

export interface Alert {
  id: string;
  createdAt?: Timestamp;
  grade: Grade;
  type: string;
  summary: string;
  clusterIds?: string[];
  platforms?: string[];
  patterns?: string[];
}

export interface Entity {
  name: string;
  role?: string;
  aliases?: string[];
}

export interface TargetConfig {
  name?: string;
  description?: string;
  keywords?: string[];
  entities?: Entity[];
  sources?: {
    naver?: boolean;
    youtube?: boolean;
    rss?: boolean;
    sites?: string[];
  };
  schedule?: { collectEveryMin?: number; reportDaily?: string; reportWeekly?: string };
}

export interface Report {
  id: string;
  type: "daily" | "weekly";
  period: string;
  generatedAt?: Timestamp;
  totals?: { mentions: number; uniqueIssues: number; alerts: number };
  bodyMarkdown: string;
}
