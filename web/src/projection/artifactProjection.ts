import type { Artifact } from '../api';

export type DeliveryClass = 'export_package' | 'report' | 'business_output' | 'internal';
export type ArtifactDirectory = 'exports' | 'governance' | 'compliance' | 'listings' | 'catalog' | 'reports' | 'internal';
export type PreviewMode = 'markdown' | 'structured_summary' | 'download_only';

export interface ProjectedArtifact {
  artifact: Artifact;
  deliveryClass: DeliveryClass;
  directory: ArtifactDirectory;
  previewMode: PreviewMode;
  isPrimaryDelivery: boolean;
  reason: string;
}

function normalized(artifact: Artifact): string {
  return `${artifact.artifact_type} ${artifact.title} ${artifact.file_name} ${JSON.stringify(artifact.metadata || {})}`.toLowerCase();
}

function isJson(artifact: Artifact): boolean {
  return artifact.file_name.toLowerCase().endsWith('.json') || artifact.mime_type.includes('json');
}

export function projectArtifact(artifact: Artifact): ProjectedArtifact {
  const value = normalized(artifact);
  const fileName = artifact.file_name.toLowerCase();
  const isZip = fileName.endsWith('.zip') || value.includes('export_package') || value.includes('listing_export') || value.includes('导出包');
  const isInternalJson = isJson(artifact) && (value.includes('manifest') || value.includes('summary') || value.includes('meta') || value.includes('snapshot') || value.includes('retrieval'));
  const isReport = value.includes('report') || value.includes('报告') || fileName.endsWith('.md') || fileName.endsWith('.pdf');
  const isGovernance = value.includes('governance') || value.includes('review') || value.includes('审核') || value.includes('治理');
  const isCompliance = value.includes('compliance') || value.includes('policy') || value.includes('合规');
  const isListing = value.includes('listing') || value.includes('shopify') || value.includes('ebay') || value.includes('草稿');
  const isCatalog = value.includes('catalog') || value.includes('product') || value.includes('sku') || value.includes('目录');

  let deliveryClass: DeliveryClass = 'business_output';
  let directory: ArtifactDirectory = 'catalog';
  let reason = '业务结果';
  if (isZip) {
    deliveryClass = 'export_package';
    directory = 'exports';
    reason = '最终导出包';
  } else if (isInternalJson) {
    deliveryClass = 'internal';
    directory = 'internal';
    reason = '内部结构化资料';
  } else if (isGovernance) {
    deliveryClass = 'report';
    directory = 'governance';
    reason = '治理审核结果';
  } else if (isCompliance) {
    deliveryClass = 'report';
    directory = 'compliance';
    reason = '合规检查结果';
  } else if (isListing) {
    deliveryClass = 'business_output';
    directory = 'listings';
    reason = '渠道草稿';
  } else if (isCatalog) {
    deliveryClass = 'business_output';
    directory = 'catalog';
    reason = '商品目录结果';
  } else if (isReport) {
    deliveryClass = 'report';
    directory = 'reports';
    reason = '可读报告';
  }

  const previewMode: PreviewMode = isInternalJson
    ? 'structured_summary'
    : isJson(artifact)
      ? 'structured_summary'
      : isReport || artifact.mime_type.includes('text') || artifact.mime_type.includes('markdown')
        ? 'markdown'
        : 'download_only';

  return {
    artifact,
    deliveryClass,
    directory,
    previewMode,
    isPrimaryDelivery: deliveryClass === 'export_package',
    reason,
  };
}

export function projectArtifacts(artifacts: Artifact[]): ProjectedArtifact[] {
  return artifacts.map(projectArtifact).sort((left, right) => {
    const classOrder: Record<DeliveryClass, number> = { export_package: 0, report: 1, business_output: 2, internal: 3 };
    const byClass = classOrder[left.deliveryClass] - classOrder[right.deliveryClass];
    if (byClass) return byClass;
    return right.artifact.created_at.localeCompare(left.artifact.created_at);
  });
}

export function primaryExport(artifacts: Artifact[]): ProjectedArtifact | null {
  return projectArtifacts(artifacts).find((item) => item.isPrimaryDelivery) || null;
}
