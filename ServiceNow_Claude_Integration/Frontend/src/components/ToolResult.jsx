import { Component } from 'react'
import IncidentList from './renderers/IncidentList.jsx'
import IncidentDetail from './renderers/IncidentDetail.jsx'
import CatalogItems from './renderers/CatalogItems.jsx'
import CatalogItemDetail from './renderers/CatalogItemDetail.jsx'
import CatalogCategories from './renderers/CatalogCategories.jsx'
import Recommendations from './renderers/Recommendations.jsx'
import Groups from './renderers/Groups.jsx'
import UserCard from './renderers/UserCard.jsx'
import Packages from './renderers/Packages.jsx'
import HealthCard from './renderers/HealthCard.jsx'
import ApiIndex from './renderers/ApiIndex.jsx'
import JsonView from './renderers/JsonView.jsx'

const RENDERERS = {
  list_incidents: IncidentList,
  get_incident_by_number: IncidentDetail,
  list_catalog_items: CatalogItems,
  get_catalog_item: CatalogItemDetail,
  list_catalog_categories: CatalogCategories,
  get_optimization_recommendations: Recommendations,
  list_groups: Groups,
  get_user: UserCard,
  list_tool_packages: Packages,
  health: HealthCard,
  index: ApiIndex,
}

/** Picks a renderer by operation name; anything unknown falls back to raw JSON. */
export default function ToolResult({ tool, payload, fields, onFollowUp }) {
  const Renderer = RENDERERS[tool]
  const result = payload?.result ?? payload
  if (!Renderer) return <JsonView data={payload} />
  return (
    <RenderBoundary fallback={<JsonView data={payload} />}>
      <Renderer result={result} payload={payload} fields={fields} onFollowUp={onFollowUp} />
    </RenderBoundary>
  )
}

class RenderBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}
