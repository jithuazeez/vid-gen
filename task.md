# Candidate Task: Conversational Multilingual AI

# Video Platform

Build an AI platform that generates cinematic videos from conversational prompts with multilingual narration, lip
synchronization, subtitles, text overlays, and export-ready rendering. Supported languages: • English • Hindi • Marathi

- Tamil • Punjabi

## Core Objective

The platform should converse with the user to collect all required information before generation starts.

The system should ask about:

- video type
- visual style
- duration
- language
- narration tone
- subtitle requirements
- text placement
- export format
- aspect ratio

## Generation Flow

User Conversation
↓
Requirement Collection
↓
Scene Planning
↓
Video Generation
↓
Voice Generation
↓
Lip Sync
↓


Subtitle + Overlay Rendering
↓
Timeline Rendering
↓
Export

## Functional Requirements

The platform must support:

- conversational planning
- cinematic scene generation
- multilingual narration
- lip synchronization
- subtitle generation
- animated text overlays
- timeline rendering
- export generation
- conversational editing

## Language Switching

The system must support changing the language of a generated video without regenerating visual scenes.

When language changes, regenerate only:

- voice
- subtitles
- lip sync
- text overlays

## Video Requirements

The platform should:

- maintain scene continuity
- maintain character consistency
- support portrait and landscape formats


- support social-media-safe framing
- support multi-scene timelines

## Subtitle + Overlay Requirements

The system should:

- generate multilingual subtitles
- dynamically position subtitles
- avoid overlapping faces
- support animated captions
- support CTA overlays

## Backend Requirements

The backend should support:

- asynchronous rendering
- queue orchestration
- asset management
- GPU task handling
- export generation
- render state tracking

## Frontend Requirements

Frontend should include:

- conversational interface
- timeline preview
- subtitle editor
- language switch controls
- export controls
- regeneration controls

## Deliverables


Candidates should submit:

- source code
- backend APIs
- rendering pipeline
- multilingual workflow
- lip sync implementation
- deployment instructions
- architecture documentation

## Evaluation Criteria

Evaluation will focus on:

- architecture quality
- AI orchestration
- rendering pipeline quality
- multilingual handling
- scalability
- lip sync quality
- engineering quality

## System Capability Matrix

```
Module Requirement
Conversation Engine Requirement collection
Scene Engine Video scene planning
Voice Layer Multilingual narration
Lip Sync Speech synchronization
Subtitle Layer Dynamic subtitle rendering
Renderer Final export generation
Frontend Preview and editing workflows
```

