# Contributing to Lake

This guide summarizes how the team works in this repository. The full rationale is in the
[Development Plan](docs/DevelopmentPlan/DevelopmentPlan.tex) (Workflow Plan and Project
Management sections). By contributing, you agree to follow the
[Code of Conduct](CodeOfConduct.md).

## Issues

All formal action items are tracked as GitHub issues, and issues are how work is assigned.
Open one from a template under **New issue**:

| Template | Use it for |
| --- | --- |
| **Docs Update** | Adding a section or document to the project documentation |
| **Peer Review** | Feedback from another team on one of our artifacts |
| **Team Meeting** / **Supervisor Meeting** | Meeting agendas and attendance |
| **Lecture** / **TA Meeting** | Lecture and TA meeting attendance (kept in separate projects) |

A good issue:

- includes a description with everything needed to address it;
- says what **done** looks like: for code, usually a passing test or a recorded measurement;
  for a document section, meeting level 4 of the rubric and passing the deliverable's checklist;
- is estimated, and is split if it looks like more than about eight hours of work;
- has at least one assignee and, where relevant, labels and a milestone.

Design decisions that need deliberation can also be opened as issues and discussed in the
comments.

## Project Board

Project work lives on the [Lake GitHub Project](https://github.com/orgs/capstoneCEGJM/projects/1).
Cards move through **Backlog → Ready → In Progress → In Review → Done**. An issue only moves
to Ready once it has a description, an estimate and an assignee. Each deliverable has a
milestone whose due date is the internal deadline (two days before the course deadline).

## Making Changes

All changes to `main` go through a pull request. Either workflow is fine:

- **Branching:** create a branch in this repository named per
  [Conventional Branch](https://conventionalbranch.org/), e.g. `feature/node-agent-heartbeat`
  or `chore/update-ci`.
- **Forking:** work on any branch in your own fork (one fork per contributor).

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
and should be descriptive but terse, e.g. `docs(SRS): add functional requirements` or
`fix(coordinator): handle node timeout`.

`fixup!` and `squash!` commits are fine while iterating, but CI blocks the merge until they
are squashed. Before merging, run:

```sh
git rebase -i --autosquash origin/main
git push --force-with-lease
```

## Pull Requests

1. Open a pull request against `main`. The description is pre-filled from the
   [PR template](.github/pull_request_template.md): fill in each section, link the issue it
   addresses (`Closes #N` closes it on merge), and work through the checklist.
2. Address the review comments.
3. Merge once the PR has **two approvals** and CI passes.
4. Delete the working branch after merging (branching workflow).

## Documentation

Documents live under `docs/` as LaTeX (or Markdown). CI builds the PDFs for every PR that
touches `docs/`, and on merge commits them to `pdfs/` and publishes them to the
[project site](https://capstonecegjm.github.io/Lake/). Do not commit generated PDFs by hand.
To build locally, run `make` (requires `pdflatex`, and `pandoc` for Markdown documents).
