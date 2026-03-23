import datetime

from .db import Base

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    team_name = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    submissions = relationship("Submission", back_populates="owner")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)
    total_weighted_score = Column(Float)
    is_fully_feasible = Column(Boolean, default=False)
    total_feasible_count = Column(Integer, default = 0)
    category_stats = Column(String)
    processor_info = Column(String)
    resolution_time_seconds = Column(Float)
    
    owner = relationship("User", back_populates="submissions")
    instance_results = relationship("InstanceResult", back_populates="submission")

class InstanceResult(Base):
    __tablename__ = "instance_results"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    category = Column(String) # Small, Medium, Large
    instance_name = Column(String) # ex: Sol_MPVRP_S_01
    is_feasible = Column(Boolean)
    calculated_distance = Column(Float) 
    calculated_transition_cost = Column(Float) 
    errors_log = Column(String) # JSON string des erreurs
    
    submission = relationship("Submission", back_populates="instance_results")