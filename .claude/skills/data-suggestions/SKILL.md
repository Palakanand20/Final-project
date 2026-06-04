# data-suggestions

Examine the current Wiki Explorer graph and suggest new topics to add.

## Usage

Ask Claude: "suggest new topics" or "what should I add to my graph?"

## What this skill does

1. Fetches all saved graphs from the REST API
2. Analyzes the topics and categories already in the graph
3. Suggests 5-10 new related topics that would enrich the graph
4. Explains why each suggestion would be valuable

## Instructions for Claude

When this skill is invoked:

1. Call `GET http://localhost:8001/api/graphs` to list all saved graphs
2. For each saved graph, call `GET http://localhost:8001/api/graphs/<id>` to get the nodes
3. Collect all node IDs and categories from the graphs
4. Analyze the topics:
   - What subject areas are already covered?
   - What related topics are missing?
   - What would connect well to existing nodes?
5. Suggest 5-10 new topics with explanations like:
   - "Add 'Quantum Mechanics' — it connects to 3 existing nodes and would bridge your physics topics"
   - "Add 'Stephen Hawking' — directly related to Black Holes which is already in your graph"

## Example

User: "suggest new topics for my graph"

Claude should analyze existing nodes (e.g. Black Holes, General Relativity, Albert Einstein) and suggest:
- "Quantum Gravity — bridges your black hole and quantum topics"
- "Gravitational Waves — recently discovered, connects to Einstein and black holes"
- "Event Horizon Telescope — the team that photographed a black hole"
