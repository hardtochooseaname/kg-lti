// frontend/src/api.js
const API_BASE_URL = '/api'

async function request(endpoint, method = 'GET', body = null) {
  const options = { method, headers: {} }
  if (body) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  const response = await fetch(`${API_BASE_URL}${endpoint}`, options)
  if (!response.ok) {
    const errorText = await response.text()
    try {
      const errorData = JSON.parse(errorText)
      throw new Error(errorData.error)
    } catch {
      throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
    }
  }
  if (response.status === 204 || response.headers.get('Content-Length') === '0') {
    return { success: true }
  }
  return response.json()
}

export function getInitialGraph(init=true) {
  if (init) {
    return request('/graph')
  } else {
    return request('/graph?init=false')
  }
}

export function getNodeLabels() {
  return request('/schema/labels')
}
export function searchSubgraph(label, keyword) {
  return request(
    `/search?label=${encodeURIComponent(label)}&keyword=${encodeURIComponent(keyword)}`,
  )
}
export function expandNode(nodeId) {
  return request(`/expand/${nodeId}`)
}
export function addNode(nodePayload) {
  return request('/nodes', 'POST', nodePayload)
}
export function addRelationship(relPayload) {
  return request('/relationships', 'POST', relPayload)
}
export function updateNodeProperty(nodeId, properties) {
  return request(`/nodes/${nodeId}`, 'PUT', { properties })
}
export function deleteNode(nodeId) {
  return request(`/nodes/${nodeId}`, 'DELETE')
}
export function deleteRelationship(relId) {
  return request(`/relationships/${relId}`, 'DELETE')
}
