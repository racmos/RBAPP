export type CardDetailOutletContext = {
  presentation: 'page' | 'modal';
  siblings?: { setId: string; cardId: string }[];
  onClose?: () => void;
};
