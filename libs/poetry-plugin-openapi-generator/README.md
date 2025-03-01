A simple wrapper of the openapi python client generator as a poetry plugin.

This is necessary to avoid adding _all the dependencies of a python client generator_ to the service package dependency closure, causing conflicts and other nonsense.
