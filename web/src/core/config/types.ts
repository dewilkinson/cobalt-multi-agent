export interface ModelConfig {
  basic: string[];
  reasoning: string[];
}

export interface RagConfig {
  provider: string;
}

export interface Cobalt MultiagentConfig {
  rag: RagConfig;
  models: ModelConfig;
}
