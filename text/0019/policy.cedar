permit(
    principal,
    action == Action::"read",
    resource) 
when {
  (if context.sudo then Admin::"root" else principal) == resource.owner ||
  resource.isPublic
};
