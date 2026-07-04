import type { Timestamp } from "firebase/firestore";

export type Grade = "red" | "orange" | "yellow" | "none";
export type FilterTag = "전체" | "대응필요" | "주의" | "위기" | "재발";
export type Role = "admin" | "member";

export type IssueImportance = "일반" | "관찰" | "중요" | "핵심";
export type RiskLevel = "없음" | "주의" | "위기" | "긴급";
export type ResponseLevel = "무대응" | "모니터링" | "보고필요" | "대응필요" | "즉시대응";

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

export type SourceType =
  | "news" | "sns" | "community" | "video" | "official" | "blog_cafe" | "unknown";

export type CommunityContentType =
  | "original_post" | "comment" | "shared_news" | "unknown";

export type VideoContentType =
  | "youtube_video" | "youtube_shorts" | "youtube_live" | "youtube_comment" | "clip" | "unknown";

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
  latestPublishedAt?: Timestamp;
  stats?: ClusterStats;
  // 소스 분류 (2단계 이후)
  sourceType?: SourceType;
  communityContentType?: CommunityContentType;
  videoContentType?: VideoContentType;
  // 대표 기사 (뉴스 클러스터)
  latestArticleTitle?: string;
  latestArticleUrl?: string;
  representativeTitle?: string;
  // 공식 탭
  officialSource?: string;
  // 병합 신뢰도 (1.0=확실, 0.75미만=확인필요, 0.50미만=split후보)
  clusterConfidence?: number;
  // 이벤트 키 (eventKey 기반 병합 차단용)
  eventKey?: string;
  // 3-레이어 분류 (중요도/리스크/대응)
  issueImportance?: IssueImportance;
  riskLevel?: RiskLevel;
  responseLevel?: ResponseLevel;
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
