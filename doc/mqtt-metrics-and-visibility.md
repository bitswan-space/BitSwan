MQTT Pipeline Inspection & Operation Protocol
-----------------------------------------------------

The MPIOP provides a set of MQTT topics which can be used to inspect (and in the future operate) pipelines.

# To get the list of pipelines in a given pump/container:

Send `get` as the payload to:
`c/{container_id}/topology/get`

You will recieve the topology by subscribing to:

`c/{container_id}/topology`

# To get a list of components in a given pipeline:

Send `get` as the payload to:
`c/{container_id}/c/{pipeline_id}/topology/get`

You will recieve the topology by subscribing to:

`c/{container_id}/c/{pipeline_id}/topology`

# To subscribe to events flowing through a given component

Send:

```
{
  "event_count": 200
}
```

To

`c/{container_id}/c/{pipeline_id}/events/subscribe`

The next 200 events to flow out of that component will now be sent to:

`c/{container_id}/c/{pipeline_id}/events`
