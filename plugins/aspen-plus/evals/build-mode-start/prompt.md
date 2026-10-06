---
description: Building a new model from scratch is planned in stages with pass criteria
tags: [build-mode]
runs: 3
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

I want to build an Aspen Plus V15 model of a sour water stripper from scratch: about 20 t/h of
refinery sour water with roughly 2 wt% NH3 and 1 wt% H2S, steam-stripped in a column, and I need
the stripped water below 50 ppmw NH3. I have never built an electrolyte model. Let's start.
