      DIMENSION P(2),LC(2),L(40)
      DATA P/.85,.75/,LC/1H ,1H#/
      IX=12345
      IS=1
      DO 20 I=1,40
      DO 10 J=1,40
      CALL RANDU(IX,IY,R)
      IX=IY
      IF(R.GT.P(IS)) IS=3-IS
   10 L(J)=LC(IS)
   20 WRITE(6,100) (L(J),J=1,40)
  100 FORMAT(1X,40A1)
      STOP
      END
