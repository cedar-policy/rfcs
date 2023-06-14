# Cedar RFC Process

The "RFC" (request for comments) process is intended to provide a consistent and controlled path for new features to enter the Cedar language. Many changes, including bug fixes and documentation improvements, can be implemented and reviewed via the normal GitHub pull request workflow. Some changes though are "substantial", and we ask that these be put through a bit of a design process to produce a consensus among the Cedar core team and the community.

## The RFC life-cycle

An RFC goes through the following stages:

* **Pending**: when the RFC is submitted as a pull request (PR) to this repository. We use PRs to provide design feedback and come to a consensus about whether an RFC should be accepted.
* **Active**: when an RFC’s associated PR is merged. The RFC being active does not guarantee that it is currently under development. It also does not guarantee that the changes will eventually be accepted or released — it is possible that the RFC could still be rejected based on additional discussion while it is active, or based on new implementation concerns that come to light during the active phase.
* **Landed**: when an RFC's proposed changes are shipped as stable in a release.
* **Rejected**: when an RFC is officially rejected or dropped.

## When to follow this process

You need to follow this process if you intend to make "substantial" changes to Cedar (<https://github.com/cedar-policy/cedar>). If you wish to suggest changes to other cedar-adjacent repositories like [cedar-spec](https://github.com/cedar-policy/cedar-spec) or [cedar-examples](https://github.com/cedar-policy/cedar-examples), please use their respective issue lists.

What constitutes a "substantial" change is evolving based on community norms, but may include the following:

* A new feature that creates new API surface area
* Changing the semantics or behavior of an existing API
* Adding, removing, or changing the behavior of a built-in function or operator in the Cedar language, or any other Cedar syntax
* The removal of features that are already shipped as part of the release channel

Some changes do not require an RFC:

* Simple bug fixes
* Fixing objectively incorrect behavior
* Rephrasing, reorganizing or refactoring
* Addition or removal of warnings
* Improvement of error messages
* Additions only likely to be noticed by other Cedar developers, invisible to users.

If you submit a pull request to implement a new feature without going through the RFC process, it may be closed with a polite request to submit an RFC first.

## Why do you need to do this

You are suggesting new features or changes to Cedar - we appreciate your willingness to contribute! We have to carefully consider the impact of every change we make that may affect end users. These constraints and tradeoffs may not be immediately obvious to users who are proposing a change to solve a specific problem they just ran into. The RFC process serves as a way to guide you through our thought process when making changes to Cedar, so that everyone can be on the same page when discussing why these changes should or should not be made.

It's often helpful to get feedback on your concept before diving into the design details required for an RFC. You may open an issue with a `Question` label on this repo to start a high-level discussion, with the goal of eventually formulating an RFC pull request with the specific implementation design.

## What is the process?

In short, to get a major feature added to Cedar, you must first get the RFC merged into the RFC repo as a markdown file. At that point the RFC is 'active' and may be implemented with the goal of eventual inclusion into Cedar.

* Work on your proposal in a markdown file based on the template (<https://github.com/cedar-policy/rfcs/blob/main/0000-template.md>). Put care into the details: RFCs that do not present convincing motivation, demonstrate understanding of the impact of the design, or are disingenuous about the drawbacks or alternatives tend to be poorly-received. Copy your markdown file in `text/my-feature.md`, where my-feature is descriptive.
* Fork this repository and create a PR with your markdown file. We will use the PR to provide feedback, and to come to a consensus on whether the RFC should be accepted. Revisions to the RFC based on feedback should all be done in the same PR.
* Eventually, the Cedar core team will decide whether the RFC is a candidate for inclusion in Cedar.
  * For every RFC, we will have a 1 week final comment period (FCP) before accepting or rejecting the RFC. This means that once a core member of the team has commented confirming that we will accept/reject, an RFC PR must have no new substantial discussion for 1 week before we take one of the actions below.
  * An RFC may be rejected at the close of its FCP. A member of the Cedar core team will then close the RFC PR.
  * An RFC may be accepted at the close of its FCP. A core team member will merge the RFC PR, at which point the RFC will become active. Note that merging an RFC into the repo doesn't imply total acceptance. Sometimes we will reject RFCs that are in the active state and already merged. In that case, we would make a new PR to the RFC repo to mark the RFC as rejected.

## Details on Active RFCs

Once an RFC becomes active the author (or any other developer) may implement it and submit the feature as a pull request to the Cedar core repo. Becoming active is not a rubber stamp, and in particular still does not mean the feature will ultimately be merged; it does mean that the core team has agreed to it in principle and are amenable to merging it.

Furthermore, the fact that a given RFC has been accepted and is active implies nothing about what priority is assigned to its implementation, nor whether anybody is currently working on it.

Modifications to active RFCs can be done in followup PRs. We strive to write each RFC in a manner that it will reflect the final design of the feature; but the nature of the process means that we cannot expect every merged RFC to actually reflect what the end result will be at the time of the next major release; therefore we try to keep each RFC document somewhat in sync with the language feature as planned, tracking such changes via followup pull requests to the document.

## Implementing an RFC

The author of an RFC is not obligated to implement it. Of course, the RFC author (like any other developer) is welcome to post an implementation for review after the RFC has been accepted. If you are interested in working on the implementation for an active RFC, but cannot determine if someone else is already working on it, feel free to ask (e.g. by leaving a comment on the associated PR).

An active RFC should have the link to the implementation PR listed if there is one. Feedback for the actual implementation should be conducted in the implementation PR instead of the original RFC PR.

## Reviewing RFCs

Members of the core team will attempt to review open RFC PRs on a regular basis. Once the core team agrees that an RFC should be accepted/rejected, a member of the core team will leave a comment on the PR with the decision and an explanation for the decision. After the FCP, pending no further discussion, a member of the core team will close the PR (if the RFC is rejected) or merge the PR (if the RFC is accepted).

## Acknowledgments

Cedar's RFC process owes its inspiration to the [Vue RFC process](https://github.com/vuejs/rfcs), [React RFC process](https://github.com/reactjs/rfcs), and [Rust RFC process](https://github.com/rust-lang/rfcs).

## License

This project is licensed under the Apache-2.0 License.
