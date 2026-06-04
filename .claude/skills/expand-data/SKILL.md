# expand-data

Add more data to the Wiki Explorer graph on a specific topic.

## Usage

Ask Claude: "expand data on <topic>" or "add more data about <topic>"

## What this skill does

1. Asks the user for a topic if not provided
2. Fetches the Wikipedia article for that topic via the REST API
3. Expands the graph by fetching linked articles up to depth 2
4. Reports how many new nodes and edges were added

## Instructions for Claude

When this skill is invoked:

1. Ask the user: "What topic would you like to expand data on?"
2. Call the expand endpoint: `GET http://localhost:8001/api/expand?title=<topic>`
3. Then call the graph endpoint: `GET http://localhost:8001/api/graph?title=<topic>&depth=2`
4. Report the results:
   - How many nodes were fetched
   - How many edges were found
   - List the top 10 connected articles
5. Suggest saving the expanded graph with a name

## Example

User: "expand data on General Relativity"

Claude should:
- Call `/api/expand?title=General+Relativity`
- Call `/api/graph?title=General+Relativity&depth=2`
- Report: "Found 47 nodes and 89 edges. Top connections: Albert Einstein, Special Relativity, Spacetime..."
