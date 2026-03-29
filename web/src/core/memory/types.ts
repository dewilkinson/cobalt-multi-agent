export interface UserMemory {
  version: string;
  lastUpdated: string;
  user: {
    workContext: {
      summary: string;
      updatedAt: string;
    };
    personalContext: {
      summary: string;
      updatedAt: string;
    };
    topOfMind: {
      summary: string;
      updatedAt: string;
    };
  };
  history: {
    recentMonths: {
      summary: string;
      updatedAt: string;
    };
    earlierContext: {
      summary: string;
      updatedAt: string;
    };
    longTermBackground: {
      summary: string;
      updatedAt: string;
    };
  };
  facts: {
    id: string;
    content: string;
    category: string;
    confidence: number;
    importance?: number;
    provenance?: {
      instance_id: string;
      timestamp: string;
    };
    createdAt: string;
    source: string;
  }[];
}
