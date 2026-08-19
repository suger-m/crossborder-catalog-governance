import { useEffect, useState } from 'react';
import {
  api,
  type Artifact,
  type Finding,
  type ListingDraft,
  type ProductSummary,
  type ProjectMaterial,
  type ProjectResource,
} from '../api';
import { localizedMessage } from '../lib/crossborderLabels';

export interface ProjectBundle {
  materials: ProjectMaterial[];
  products: ProductSummary[];
  resources: ProjectResource[];
  listings: ListingDraft[];
  findings: Finding[];
  artifacts: Artifact[];
}

const EMPTY: ProjectBundle = {
  materials: [],
  products: [],
  resources: [],
  listings: [],
  findings: [],
  artifacts: [],
};

export function useProjectBundle(projectId: string | null) {
  const [bundle, setBundle] = useState<ProjectBundle>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const refresh = async (id = projectId) => {
    if (!id) {
      setBundle(EMPTY);
      setError('');
      return;
    }
    setLoading(true);
    try {
      const workers = [
        'catalog_steward_agent',
        'compliance_specialist_agent',
        'listing_operations_agent',
        'governance_reviewer_agent',
      ];
      const [materials, products, resources, listings, workspaces] = await Promise.all([
        api.projectMaterials(id),
        api.projectProducts(id),
        api.projectResources(id),
        api.projectListings(id),
        Promise.all(workers.map((worker) => api.agentWorkspace(id, worker).catch(() => null))),
      ]);
      const artifactMap = new Map<string, Artifact>();
      const findings: Finding[] = [];
      workspaces.forEach((workspace) => {
        workspace?.artifacts?.forEach((item) => artifactMap.set(item.id, item));
        workspace?.findings?.forEach((item) => findings.push(item));
      });
      setBundle({
        materials: materials.items,
        products: products.items,
        resources: resources.items,
        listings: listings.items,
        findings,
        artifacts: Array.from(artifactMap.values()),
      });
      setError('');
    } catch (reason) {
      setError(localizedMessage(reason));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh(projectId);
  }, [projectId]);

  return { bundle, loading, error, refresh };
}
