# Agent skill access

All 12 built-in zomega agents have access to the same enabled skill catalog.

Each `agent.yaml` declares:

```yaml
skills: ["*"]
```

The wildcard is resolved by `zomega.catalog.resolve_agent_skills()` to every currently enabled public skill. This keeps agent capability access synchronized automatically when skills are added or disabled.

## Default workflow is unchanged

`skills` describes what an agent is allowed to use. `default_workflow` describes the smaller role-specific sequence used by a normal agent run.

Keeping these concepts separate prevents a normal agent run from automatically executing the entire 100-skill catalog while still making every agent advertise the same complete capability set.

## Catalog behavior

`GET /v1/agents` and the agent entries in `GET /v1/catalog` expose the resolved `skills` list plus `skill_count` for each agent. Internal prompts, validation rules, and permission details remain excluded from the public catalog.
