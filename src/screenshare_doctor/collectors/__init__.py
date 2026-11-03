"""Collectors read facts and never decide what they mean.

A collector that cannot read something records a :class:`~screenshare_doctor.models.ProbeFailure`
instead of raising, so one broken tool never hides what the others found.
"""
